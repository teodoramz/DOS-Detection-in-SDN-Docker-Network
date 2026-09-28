"""Pin checks that would otherwise only fail at runtime inside a container."""
import re
from pathlib import Path

import pytest

WORKER = Path("build/worker/requirements.txt").read_text()
COLLECTOR = Path("build/collector/Dockerfile").read_text()
RYU = Path("build/ryu-controller/requirements.txt").read_text()


def kafka_version(text):
    match = re.search(r"kafka-python(?:-ng)?==([0-9.]+)", text)
    assert match, f"no kafka client pin found in:\n{text}"
    return tuple(int(p) for p in match.group(1).split("."))


@pytest.mark.parametrize("name,text", [("worker", WORKER), ("collector", COLLECTOR)])
def test_python312_images_use_a_compatible_kafka_client(name, text):
    """kafka-python below 2.1 imports kafka.vendor.six.moves, gone in 3.12."""
    assert kafka_version(text) >= (2, 1), f"{name} pins a kafka client too old for Python 3.12"


def test_the_controller_runs_on_python39_where_the_old_client_is_fine():
    assert "3.9-slim" in Path("build/ryu-controller/Dockerfile").read_text()
    assert kafka_version(RYU) >= (2, 0)


def test_worker_pins_every_library_it_imports():
    for package in ("pandas", "numpy", "scikit-learn", "joblib", "minio", "xgboost",
                    "imbalanced-learn"):
        assert re.search(rf"^{re.escape(package)}==", WORKER, re.M), f"{package} unpinned"


def test_worker_image_provides_the_unversioned_libpcap():
    """jnetpcap's native library links against libpcap.so, which the runtime
    package does not ship -- only libpcap.so.1. Without it the converter dies
    with UnsatisfiedLinkError."""
    dockerfile = Path("build/worker/Dockerfile").read_text()
    assert "libpcap-dev" in dockerfile


def test_worker_image_ships_the_converter_and_its_native_library():
    dockerfile = Path("build/worker/Dockerfile").read_text()
    assert "COPY cicflowmeter" in dockerfile
    assert Path("build/worker/cicflowmeter/lib/native/libjnetpcap.so").is_file()
    assert Path("build/worker/cicflowmeter/lib/CICFlowMeter-4.0.jar").is_file()


def test_worker_image_has_a_java_runtime():
    assert "default-jre-headless" in Path("build/worker/Dockerfile").read_text()
