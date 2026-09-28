"""A collector must wait for its dependencies, never crash.

restart: unless-stopped recreates the network namespace, which destroys the
veth the topology scripts attached, and the container never recovers.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path("build/collector")))

from collector import connect_with_retry


class Sleeper:
    def __init__(self):
        self.slept = []

    def __call__(self, seconds):
        self.slept.append(seconds)


def test_returns_the_resource_on_the_first_try():
    assert connect_with_retry(lambda: "minio", what="minio", sleeper=Sleeper()) == "minio"


def test_retries_until_the_dependency_appears():
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        if calls["n"] < 5:
            raise OSError("connection refused")
        return "up"

    sleeper = Sleeper()
    assert connect_with_retry(factory, what="minio", sleeper=sleeper) == "up"
    assert len(sleeper.slept) == 4


def test_retries_forever_by_default():
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        if calls["n"] < 40:
            raise OSError("down")
        return "up"

    assert connect_with_retry(factory, what="kafka", sleeper=Sleeper()) == "up"


def test_entrypoint_silences_the_missing_device_message():
    """The wait loop runs twice a second; its stderr must not fill the log."""
    text = Path("build/collector/entrypoint.sh").read_text()
    assert "2>/dev/null" in text


@pytest.mark.parametrize("script", ["build/collector/entrypoint.sh",
                                    "build/worker/entrypoint.sh"])
def test_entrypoint_waits_rather_than_exiting(script):
    text = Path(script).read_text()
    assert "while" in text
    assert "WAIT_FOR_IP" in text
