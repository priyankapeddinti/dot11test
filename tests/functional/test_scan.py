import logging

import pytest

log = logging.getLogger(__name__)
pytestmark = pytest.mark.functional


def test_wifi_toggle(device):
    device.wifi.set_enabled(False)
    assert device.wifi.status().enabled is False
    device.wifi.set_enabled(True)
    assert device.wifi.status().enabled is True


def test_scan_returns_results(wifi_on):
    results = wifi_on.scan_and_wait(timeout=20)
    log.info("scan returned %d results", len(results))
    assert results, "No scan results returned"
    sample = results[0]
    assert sample.bssid
    assert sample.frequency_mhz > 0
    assert sample.rssi_dbm < 0


def test_expected_ssid_visible(wifi_on, config):
    networks = config.require("networks")
    expected = {n["ssid"] for n in networks if isinstance(n, dict) and "ssid" in n}
    seen = {r.ssid for r in wifi_on.scan_and_wait(timeout=20)}
    missing = expected - seen
    assert not missing, f"Configured SSIDs not seen in scan: {missing}"
