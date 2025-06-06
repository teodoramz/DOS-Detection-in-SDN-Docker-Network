# -*- coding: utf-8 -*-
"""
dns_live_monitor_scapy_verbose.py – Pure-Python DrDoS DNS detector
==================================================================
* Fără CICFlowMeter: totul în Scapy + pandas.
* Agregă fluxurile unidirecționale și calculează exact cele 30 de
  feature-uri pe care modelul le așteaptă.
* Log DEBUG – vezi totul în `docker logs`.

Dependențe:
    pip install scapy pandas joblib numpy
Rulare:
    sudo python dns_live_monitor_scapy_verbose.py
"""
from __future__ import annotations
import logging, sys, time
from pathlib import Path
from datetime import datetime, UTC
import numpy as np
import pandas as pd
import joblib
from scapy.all import sniff, IP, UDP, TCP 


MODEL_PATH   = Path('/app/dnsmodel.joblib')
DNS_IP       = '10.0.1.2'       
INTERFACE    = 'eth0'         
INTERVAL_SEC = 100              
THRESHOLD    = 0.01             

BASE_FEATURES = [
    'Inbound','Min Packet Length','Fwd Packet Length Min','Source Port',
    'Fwd Packet Length Mean','Average Packet Size','Avg Fwd Segment Size',
    'Packet Length Mean','Protocol','Flow Bytes/s','Down/Up Ratio',
    'URG Flag Count','Flow Packets/s','Fwd Packets/s','Destination Port',
    'CWE Flag Count','ACK Flag Count','Fwd Packet Length Max','Max Packet Length',
    'Bwd Packet Length Min','Init_Win_bytes_forward','Fwd PSH Flags','RST Flag Count',
    'Bwd Packet Length Mean','Avg Bwd Segment Size','Bwd IAT Min','Flow Duration',
    'Init_Win_bytes_backward','Fwd IAT Total','Bwd Packet Length Max'
]
INPUT_COLS = ['Source IP'] + BASE_FEATURES

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)


class FlowStats:
    """Statistici unidirecționale pentru un flow."""
    __slots__ = ('src','dst','sport','dport','proto','dir_fwd',
                 'lens_fwd','lens_bwd','ts',
                 'urg','ack','rst','psh',
                 'win_fwd','win_bwd')

    def __init__(self, src, dst, sport, dport, proto):
        self.src, self.dst, self.sport, self.dport, self.proto = src,dst,sport,dport,proto
        self.dir_fwd = (src, dst)
        self.lens_fwd, self.lens_bwd = [], []
        self.ts = []
        self.urg = self.ack = self.rst = self.psh = 0
        self.win_fwd = self.win_bwd = 0


    def add(self, pkt):
        length = len(pkt)
        self.ts.append(pkt.time)
        direction = 'fwd' if (pkt[IP].src, pkt[IP].dst) == self.dir_fwd else 'bwd'
        (self.lens_fwd if direction == 'fwd' else self.lens_bwd).append(length)

        if TCP in pkt:
            flags = pkt[TCP].flags
            if 'U' in flags: self.urg += 1
            if 'A' in flags: self.ack += 1
            if 'R' in flags: self.rst += 1
            if 'P' in flags: self.psh += 1
            win = pkt[TCP].window
            if direction == 'fwd' and not self.win_fwd:
                self.win_fwd = win
            if direction == 'bwd' and not self.win_bwd:
                self.win_bwd = win


    def to_row(self):
        if not self.ts:
            return None
        dur = max(self.ts) - min(self.ts) or 1e-6
        tot_pkts   = len(self.lens_fwd) + len(self.lens_bwd)
        tot_bytes  = sum(self.lens_fwd) + sum(self.lens_bwd)
        avg_pkt    = tot_bytes / tot_pkts if tot_pkts else 0
        inbound    = int(self.dst == DNS_IP)
        down_up    = sum(self.lens_bwd) / (sum(self.lens_fwd) or 1)
        flow_ps    = tot_pkts / dur
        fwd_ps     = len(self.lens_fwd) / dur if self.lens_fwd else 0
        bytes_sec  = tot_bytes / dur

        return {
            'Source IP'              : self.src,
            'Inbound'                : inbound,
            'Min Packet Length'      : min(self.lens_fwd + self.lens_bwd),
            'Fwd Packet Length Min'  : min(self.lens_fwd) if self.lens_fwd else 0,
            'Source Port'            : self.sport,
            'Fwd Packet Length Mean' : np.mean(self.lens_fwd) if self.lens_fwd else 0,
            'Average Packet Size'    : avg_pkt,
            'Avg Fwd Segment Size'   : np.mean(self.lens_fwd) if self.lens_fwd else 0,
            'Packet Length Mean'     : avg_pkt,
            'Protocol'               : self.proto,
            'Flow Bytes/s'           : bytes_sec,
            'Down/Up Ratio'          : down_up,
            'URG Flag Count'         : self.urg,
            'Flow Packets/s'         : flow_ps,
            'Fwd Packets/s'          : fwd_ps,
            'Destination Port'       : self.dport,
            'CWE Flag Count'         : 0,
            'ACK Flag Count'         : self.ack,
            'Fwd Packet Length Max'  : max(self.lens_fwd) if self.lens_fwd else 0,
            'Max Packet Length'      : max(self.lens_fwd + self.lens_bwd),
            'Bwd Packet Length Min'  : min(self.lens_bwd) if self.lens_bwd else 0,
            'Init_Win_bytes_forward' : self.win_fwd,
            'Fwd PSH Flags'          : self.psh,
            'RST Flag Count'         : self.rst,
            'Bwd Packet Length Mean' : np.mean(self.lens_bwd) if self.lens_bwd else 0,
            'Avg Bwd Segment Size'   : np.mean(self.lens_bwd) if self.lens_bwd else 0,
            'Bwd IAT Min'            : 0,
            'Flow Duration'          : dur * 1e6,   # μs
            'Init_Win_bytes_backward': self.win_bwd,
            'Fwd IAT Total'          : 0,
            'Bwd Packet Length Max'  : max(self.lens_bwd) if self.lens_bwd else 0
        }


def collect_flows() -> pd.DataFrame:
    flows: dict[tuple, FlowStats] = {}

    def _proc(pkt):
        if IP not in pkt:
            return
        if pkt[IP].dst != DNS_IP and pkt[IP].src != DNS_IP:
            return
        proto = 17 if UDP in pkt else 6 if TCP in pkt else pkt[IP].proto
        sport = pkt[UDP].sport if UDP in pkt else pkt[TCP].sport if TCP in pkt else 0
        dport = pkt[UDP].dport if UDP in pkt else pkt[TCP].dport if TCP in pkt else 0
        key   = (pkt[IP].src, pkt[IP].dst, sport, dport, proto)
        flows.setdefault(key, FlowStats(*key)).add(pkt)

    sniff(
        iface   = INTERFACE,
        store   = False,
        timeout = INTERVAL_SEC,
        prn     = _proc,
        filter  = f'host {DNS_IP} and port 53'
    )

    rows = [f.to_row() for f in flows.values() if f.to_row()]
    return pd.DataFrame(rows)

def main():
    if not MODEL_PATH.exists():
        logging.critical('❌  Model absent: %s', MODEL_PATH)
        sys.exit(1)

    pipe = joblib.load(MODEL_PATH)
    try:
        expected_cols = list(pipe.named_steps['prep'].feature_names_in_)
    except Exception:
        expected_cols = BASE_FEATURES.copy()

    logging.info('Model loaded. It expects %d features.', len(expected_cols))
    logging.info('Monitoring DNS %s on %s | interval=%ds | thr=%.2f',
                 DNS_IP, INTERFACE, INTERVAL_SEC, THRESHOLD)

    while True:
        try:
            df = collect_flows()
            logging.debug('Flows captured: %d', len(df))
            if df.empty:
                continue

            for col in expected_cols:
                if col not in df:
                    df[col] = 0.0
            feats = df[expected_cols].fillna(0)

            proba = pipe.predict_proba(feats)[:, 1]
            df['prob'] = proba

            sus = df[df['prob'] >= THRESHOLD]
            if sus.empty:
                logging.info('No suspicious flows.')
            else:
                logging.warning('‼︎ %d suspicious flows', len(sus))
                for _, r in sus.iterrows():
                    logging.warning('Suspicious %s → p=%.3f', r['Source IP'], r['prob'])

        except KeyboardInterrupt:
            logging.info('Interrupted → exiting.')
            break
        except Exception as exc:
            logging.exception(exc)
        finally:
            time.sleep(1)

if __name__ == '__main__':
    main()
