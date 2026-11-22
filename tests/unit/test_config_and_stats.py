import json
from pathlib import Path

import pytest

from dot11test import stats
from dot11test.config import ConfigError, load_config
from dot11test.types import ScanResult

pytestmark = pytest.mark.unit

EXAMPLE = Path(__file__).resolve().parents[2] / "config" / "config.example.yaml"


def test_example_config_loads():
    cfg = load_config(EXAMPLE)
    assert cfg.get("platform") in {"android", "ios"}
    networks = cfg.require("networks")
    assert isinstance(networks, list) and all("ssid" in n for n in networks)


def test_get_and_require(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("iperf:\n  server: 1.2.3.4\n  port: 5201\n")
    cfg = load_config(p)
    assert cfg.get("iperf", "server") == "1.2.3.4"
    assert cfg.get("iperf", "missing", default=9) == 9
    assert cfg.get("iperf", "server", "deeper") is None
    with pytest.raises(ConfigError, match="ping.target"):
        cfg.require("ping", "target")


def test_env_var_path(tmp_path, monkeypatch):
    p = tmp_path / "env.yaml"
    p.write_text("platform: ios\n")
    monkeypatch.setenv("DOT11_CONFIG", str(p))
    assert load_config().get("platform") == "ios"


def test_missing_config(tmp_path):
    with pytest.raises(ConfigError, match="Config not found"):
        load_config(tmp_path / "nope.yaml")


def test_empty_config(tmp_path):
    p = tmp_path / "empty.yaml"
    p.write_text("")
    assert load_config(p).raw == {}


def test_record_writes_json(tmp_path, monkeypatch):
    monkeypatch.setattr(stats, "RESULTS_DIR", tmp_path / "results")
    path = stats.record("tcp downlink", {"scan": ScanResult("aa", 5180, -50, "x"), "mbps": 9.5})
    data = json.loads(path.read_text())
    assert path.name.endswith("_tcp_downlink.json")
    assert data["name"] == "tcp downlink"
    assert data["mbps"] == 9.5
    assert data["scan"]["frequency_mhz"] == 5180


@pytest.mark.parametrize("freq,band", [(2412, "2.4GHz"), (5745, "5GHz"), (6435, "6GHz"), (900, "unknown")])
def test_scan_band(freq, band):
    assert ScanResult("aa", freq, -50, "x").band == band
