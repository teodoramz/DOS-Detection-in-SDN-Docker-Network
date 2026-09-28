"""The worker starts before its interface exists, so it must wait, not crash.

A crash plus restart: unless-stopped recreates the network namespace and
destroys the veth the topology scripts attached.
"""
from pathlib import Path

import pytest

from ddos_worker.main import connect_with_retry


class Sleeper:
    def __init__(self):
        self.slept = []

    def __call__(self, seconds):
        self.slept.append(seconds)


def test_returns_the_resource_on_the_first_try():
    assert connect_with_retry(lambda: "broker", what="kafka", sleeper=Sleeper()) == "broker"


def test_retries_until_the_resource_appears():
    attempts = {"n": 0}

    def factory():
        attempts["n"] += 1
        if attempts["n"] < 4:
            raise OSError("no route to host")
        return "broker"

    sleeper = Sleeper()
    assert connect_with_retry(factory, what="kafka", sleeper=sleeper) == "broker"
    assert attempts["n"] == 4
    assert len(sleeper.slept) == 3


def test_waits_between_attempts():
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        if calls["n"] < 2:
            raise OSError("down")
        return "ok"

    sleeper = Sleeper()
    connect_with_retry(factory, what="kafka", delay=7, sleeper=sleeper)
    assert sleeper.slept == [7]


def test_gives_up_after_the_attempt_limit():
    def factory():
        raise OSError("never comes up")

    with pytest.raises(OSError):
        connect_with_retry(factory, what="kafka", attempts=3, sleeper=Sleeper())


def test_retries_forever_when_no_limit_is_given():
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        if calls["n"] < 50:
            raise OSError("down")
        return "ok"

    assert connect_with_retry(factory, what="kafka", attempts=0, sleeper=Sleeper()) == "ok"


def test_worker_entrypoint_waits_for_its_address():
    script = Path("build/worker/entrypoint.sh")
    assert script.is_file()
    assert "WAIT_FOR_IP" in script.read_text()


def test_worker_dockerfile_uses_the_entrypoint():
    assert "entrypoint.sh" in Path("build/worker/Dockerfile").read_text()


def test_compose_tells_each_worker_which_address_to_wait_for():
    yaml = pytest.importorskip("yaml")
    host2 = yaml.safe_load(Path("docker-compose-host2.yml").read_text())
    expected = {"worker1": "10.0.5.11", "worker2": "10.0.5.12", "worker3": "10.0.5.13"}
    for name, ip in expected.items():
        assert "WAIT_FOR_IP" in host2["services"][name]["environment"], name
