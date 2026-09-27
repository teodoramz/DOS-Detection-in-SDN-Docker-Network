"""Structural checks on the compose manifests."""
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

HOST1 = yaml.safe_load(Path("docker-compose-host1.yml").read_text())
HOST2 = yaml.safe_load(Path("docker-compose-host2.yml").read_text())
ALL = {**HOST1["services"], **HOST2["services"]}


def test_every_service_that_builds_declares_a_build_key():
    for name, svc in ALL.items():
        assert "build" in svc or "image" in svc, f"{name} has neither build nor image"
        assert "context" not in svc, f"{name} has a stray top-level context"


def test_every_build_context_exists():
    for name, svc in ALL.items():
        if "build" in svc:
            build = svc["build"]
            context = build["context"] if isinstance(build, dict) else build
            assert Path(context).is_dir(), f"{name} builds missing context {context}"


def test_no_service_uses_docker_networking():
    for name, svc in ALL.items():
        assert svc.get("network_mode") in ("none", "host"), f"{name} uses docker networking"
    assert "networks" not in HOST1 and "networks" not in HOST2


def test_ryu_runs_on_the_host_network_without_a_port_mapping():
    ryu = HOST1["services"]["ryu"]
    assert ryu["network_mode"] == "host"
    assert "ports" not in ryu


def test_the_three_workers_build_the_worker_image_one_per_layer():
    layers = []
    for name in ("worker1", "worker2", "worker3"):
        svc = HOST2["services"][name]
        assert svc["build"]["context"] == "./build/worker"
        assert "command" not in svc
        layers.append(svc["environment"]["WORKER_LAYER"])
    assert sorted(layers) == ["bottom", "inter", "top"]


def test_the_three_collectors_build_the_collector_image_one_per_layer():
    layers = []
    for name in ("dns_collector", "proxy_collector", "web_collector"):
        svc = HOST1["services"][name]
        assert svc["build"]["context"] == "./build/collector"
        layers.append(svc["environment"]["LAYER"])
    assert sorted(layers) == ["bottom", "inter", "top"]


def test_collectors_take_the_capture_window_from_the_environment():
    for name in ("dns_collector", "proxy_collector", "web_collector"):
        assert HOST1["services"][name]["environment"]["CAPTURE_DURATION"] == "${CAPTURE_DURATION}"


def test_host1_has_the_four_switches_and_host2_has_the_fifth():
    assert {"sw1", "sw2", "sw3", "sw4"} <= set(HOST1["services"])
    assert "sw5" in HOST2["services"]


def test_host2_carries_the_services_it_should():
    expected = {"kafka", "kafdrop", "minio", "worker1", "worker2", "worker3", "sw5"}
    assert expected <= set(HOST2["services"])


def test_ryu_gets_the_blocker_environment():
    env = HOST1["services"]["ryu"]["environment"]
    for key in ("KAFKA_BROKER", "KAFKA_ALERT_TOPIC", "BLOCK_HARD_TIMEOUT",
                "BLOCK_PRIORITY", "BLOCK_WHITELIST", "LAYER_DATAPATH_MAP"):
        assert key in env, f"ryu is missing {key}"
