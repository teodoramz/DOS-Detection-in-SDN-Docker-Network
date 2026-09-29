"""Guards for the remaining review findings."""
import re
from pathlib import Path

CI = Path(".github/workflows/tests.yml").read_text()


def test_ci_installs_everything_the_tests_import():
    """importorskip made ten env-generation tests vanish silently in CI."""
    install = next(l for l in CI.splitlines() if "pip install pytest" in l)
    for package in ("jinja2", "pyyaml", "pandas", "numpy", "joblib", "scikit-learn"):
        assert package in install, f"CI does not install {package}"


def test_no_test_uses_importorskip_for_a_ci_installed_package():
    for path in Path("tests").glob("test_*.py"):
        for name in ("jinja2", "yaml"):
            if f'importorskip("{name}")' in path.read_text():
                assert name in CI or name == "yaml", f"{path.name} skips on {name}"


def test_java_disables_log4j_message_lookups():
    """This JVM parses hostile pcaps; the vendored log4j-core is 2.11.0."""
    for path in ("build/worker/Dockerfile", "startup/templates/env.j2"):
        assert "formatMsgNoLookups" in Path(path).read_text(), f"{path}"


def test_the_alert_window_has_a_real_end():
    source = Path("build/worker/ddos_worker/main.py").read_text()
    assert "window_end_for" in source, "window_end still equals window_start"


def test_env_generation_tests_do_not_touch_the_repo_env():
    """Running pytest on a deployed host must not rewrite its live .env."""
    text = Path("tests/test_env_generation.py").read_text()
    assert "DDOS_DETECTION_HOME" in text
    assert "tmp_path" in text or "tmp_path_factory" in text
    assert re.search(r'Path\("\.env"\)', text) is None, "reads the repo-root .env"
