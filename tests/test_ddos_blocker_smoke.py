"""ddos_blocker.py imports ryu, which is not installed here. Check its shape."""
import ast
from pathlib import Path

SOURCE = Path("build/ryu-controller/ddos_ryu/ddos_blocker.py")


def tree():
    return ast.parse(SOURCE.read_text())


def classes():
    return {n.name: n for n in ast.walk(tree()) if isinstance(n, ast.ClassDef)}


def methods(name):
    return {n.name for n in ast.walk(classes()[name]) if isinstance(n, ast.FunctionDef)}


def test_module_parses():
    assert tree() is not None


def test_defines_the_app_and_the_rest_controller():
    assert "DDoSBlocker" in classes()
    assert "DDoSRestController" in classes()


def test_app_handles_the_events_a_learning_switch_needs():
    assert "switch_features_handler" in methods("DDoSBlocker")
    assert "packet_in_handler" in methods("DDoSBlocker")


def test_app_consumes_alerts_and_installs_blocks():
    assert "_alert_loop" in methods("DDoSBlocker")
    assert "apply_alert" in methods("DDoSBlocker")


def test_app_can_remove_a_block():
    assert "remove_block" in methods("DDoSBlocker")


def test_rest_controller_exposes_the_documented_routes():
    source = SOURCE.read_text()
    for route in ("/ddos/blocks", "/ddos/status"):
        assert route in source


def test_app_uses_the_shared_block_logic_rather_than_its_own():
    source = SOURCE.read_text()
    assert "from .blocking import" in source
    assert "from .config import" in source


def test_dockerfile_runs_ofctl_rest_alongside_the_blocker():
    dockerfile = Path("build/ryu-controller/Dockerfile").read_text()
    assert "ryu.app.ofctl_rest" in dockerfile
    assert "ddos_blocker" in dockerfile
