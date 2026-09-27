"""The MinIO image is distroless, so its interface is configured from the host."""
from pathlib import Path

SCRIPT = Path("host2/3.sw5-containers.sh").read_text()


def minio_block():
    start = SCRIPT.index("# minio")
    rest = SCRIPT[start:]
    end = rest.find("# worker1")
    return rest[:end if end > 0 else len(rest)]


def test_minio_interface_is_configured_from_the_host():
    block = minio_block()
    assert "nsenter" in block, "minio has no shell or ip binary; use nsenter from the host"


def test_no_docker_exec_ip_against_minio():
    for line in minio_block().splitlines():
        assert not line.strip().startswith("docker exec minio ip"), line.strip()


def test_minio_still_gets_both_addresses_and_a_route():
    block = minio_block()
    assert "10.0.5.9/24" in block
    assert "10.255.255.101/24" in block
    assert "10.0.5.1" in block


def test_the_switch_side_still_uses_docker_exec():
    assert "docker exec sw5 ovs-vsctl add-port br-sw5 eth_s3" in minio_block()
