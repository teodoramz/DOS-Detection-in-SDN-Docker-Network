"""Ryu application: forward the network, and drop what the workers flag.

The bridges run fail-mode=secure, so without a controller installing flows
nothing forwards at all; the MAC-learning logic here is what makes the testbed
a working network. On top of that it consumes alerts from Kafka and installs
source-IP drop rules on the switch for the layer that raised them.
"""

from __future__ import annotations

import json
import os

from ryu.app.wsgi import ControllerBase, Response, WSGIApplication, route
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.lib import hub
from ryu.lib.packet import ether_types, ethernet, packet
from ryu.ofproto import ofproto_v1_3

from .blocking import (
    ETH_TYPE_IPV4,
    LEARNED_PRIORITY,
    TABLE_MISS_PRIORITY,
    BlockTable,
    build_block_flow,
    decide,
)
from .config import BlockerConfig

INSTANCE_NAME = "ddos_blocker_app"
LEARNED_IDLE_TIMEOUT = 60


class DDoSBlocker(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {"wsgi": WSGIApplication}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cfg = BlockerConfig.from_env(os.environ)
        self.mac_to_port = {}
        self.datapaths = {}
        self.blocks = BlockTable()
        self.alerts_seen = 0
        self.blocks_installed = 0

        kwargs["wsgi"].register(DDoSRestController, {INSTANCE_NAME: self})

        self.logger.info(
            "blocker: topic=%s broker=%s timeout=%ss priority=%s layers=%s",
            self.cfg.alert_topic, self.cfg.kafka_broker,
            self.cfg.block_timeout, self.cfg.block_priority, self.cfg.layer_dpid,
        )
        self.alert_thread = hub.spawn(self._alert_loop)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        self.datapaths[datapath.id] = datapath

        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self._add_flow(datapath, TABLE_MISS_PRIORITY, parser.OFPMatch(), actions)
        self.logger.info("datapath %016x connected", datapath.id)

    def _add_flow(self, datapath, priority, match, actions, idle_timeout=0):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        instructions = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        datapath.send_msg(parser.OFPFlowMod(
            datapath=datapath, priority=priority, match=match,
            instructions=instructions, idle_timeout=idle_timeout,
        ))

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        in_port = msg.match["in_port"]

        eth = packet.Packet(msg.data).get_protocols(ethernet.ethernet)[0]
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        self.mac_to_port.setdefault(datapath.id, {})[eth.src] = in_port
        out_port = self.mac_to_port[datapath.id].get(eth.dst, ofproto.OFPP_FLOOD)
        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=eth.dst, eth_src=eth.src)
            self._add_flow(datapath, LEARNED_PRIORITY, match, actions,
                           idle_timeout=LEARNED_IDLE_TIMEOUT)

        data = msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
        datapath.send_msg(parser.OFPPacketOut(
            datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port,
            actions=actions, data=data,
        ))

    def apply_alert(self, alert: dict) -> dict:
        self.alerts_seen += 1

        decision = decide(alert, self.cfg)
        if decision is None:
            self.logger.warning("ignoring alert, nothing to block: %s", alert)
            return {"blocked": False, "reason": "refused"}

        datapath = self.datapaths.get(decision.dpid)
        if datapath is None:
            self.logger.warning(
                "datapath %s for layer %s is not connected", decision.dpid, decision.layer
            )
            return {"blocked": False, "reason": "datapath not connected"}

        is_new = self.blocks.record(decision.dpid, decision.source_ip, self.cfg.block_timeout)
        datapath.send_msg(build_block_flow(datapath, decision, self.cfg))
        self.blocks_installed += 1

        self.logger.warning(
            "%s %s on datapath %016x for %ss (layer %s)",
            "BLOCK" if is_new else "REFRESH",
            decision.source_ip, decision.dpid, self.cfg.block_timeout, decision.layer,
        )
        return {
            "blocked": True, "new": is_new,
            "source_ip": decision.source_ip, "dpid": decision.dpid,
        }

    def remove_block(self, dpid: int, ip: str) -> bool:
        datapath = self.datapaths.get(dpid)
        if datapath is None:
            return False
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        datapath.send_msg(parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY,
            priority=self.cfg.block_priority,
            match=parser.OFPMatch(eth_type=ETH_TYPE_IPV4, ipv4_src=ip),
        ))
        return self.blocks.forget(dpid, ip)

    def _alert_loop(self):
        """Consume alerts in a green thread so Ryu's eventlet loop keeps running."""
        from kafka import KafkaConsumer

        while True:
            try:
                consumer = KafkaConsumer(
                    self.cfg.alert_topic,
                    bootstrap_servers=[self.cfg.kafka_broker],
                    group_id="ryu-blocker",
                    auto_offset_reset="latest",
                    enable_auto_commit=True,
                    consumer_timeout_ms=1000,
                )
                self.logger.info(
                    "consuming %s from %s", self.cfg.alert_topic, self.cfg.kafka_broker
                )
                while True:
                    for record in consumer:
                        try:
                            alert = json.loads(record.value.decode("utf-8"))
                        except (ValueError, AttributeError, UnicodeDecodeError):
                            self.logger.warning(
                                "skipping malformed alert: %r", record.value[:200]
                            )
                            continue
                        self.apply_alert(alert)
                    hub.sleep(0.5)
            except Exception as exc:
                self.logger.error("alert consumer failed, retrying in 5s: %s", exc)
                hub.sleep(5)


class DDoSRestController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super().__init__(req, link, data, **config)
        self.app = data[INSTANCE_NAME]

    def _json(self, payload, status=200):
        return Response(content_type="application/json", status=status,
                        body=json.dumps(payload, default=str))

    @route("ddos", "/ddos/status", methods=["GET"])
    def status(self, req, **kwargs):
        return self._json({
            "datapaths": [f"{dpid:016x}" for dpid in sorted(self.app.datapaths)],
            "alerts_seen": self.app.alerts_seen,
            "blocks_installed": self.app.blocks_installed,
            "active_blocks": len(self.app.blocks.active()),
            "block_timeout_s": self.app.cfg.block_timeout,
            "layer_datapath_map": self.app.cfg.layer_dpid,
        })

    @route("ddos", "/ddos/blocks", methods=["GET"])
    def list_blocks(self, req, **kwargs):
        return self._json({"blocks": self.app.blocks.active()})

    @route("ddos", "/ddos/blocks", methods=["POST"])
    def add_block(self, req, **kwargs):
        try:
            body = json.loads(req.body.decode("utf-8"))
        except ValueError:
            return self._json({"error": "body must be JSON"}, status=400)
        result = self.app.apply_alert(body)
        return self._json(result, status=200 if result.get("blocked") else 400)

    @route("ddos", "/ddos/blocks/{ip}", methods=["DELETE"])
    def delete_block(self, req, ip, **kwargs):
        removed = [
            entry for entry in self.app.blocks.active()
            if entry["source_ip"] == ip and self.app.remove_block(entry["dpid"], ip)
        ]
        return self._json({"removed": len(removed), "source_ip": ip})
