"""The harness itself: both package roots must be importable."""
import importlib

import pytest


@pytest.mark.parametrize("module", ["ddos_worker", "ddos_ryu"])
def test_package_importable(module):
    assert importlib.import_module(module) is not None
