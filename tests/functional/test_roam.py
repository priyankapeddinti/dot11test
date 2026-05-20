import logging
import time

import pytest

log = logging.getLogger(__name__)
pytestmark = pytest.mark.functional


def test_roam_between_bssids(device, config):
    """Observe a BSSID change while staying on the same SSID.

    Requires two APs broadcasting the same SSID listed under networks.roam.bssids.
    The test connects, then waits up to `timeout` seconds for the device to
    associate with a different BSSID than the initial one. Forcing a roam is
    vendor-specific, so this test is observational unless you trigger it
    externally (e.g. disable the current radio).
    """
    roam_cfg = config.get("networks", "roam")
    if not roam_cfg or len(roam_cfg.get("bssids", [])) < 2:
        pytest.skip("networks.roam not configured with >=2 bssids")

    ssid = roam_cfg["ssid"]
    expected_bssids = {b.lower() for b in roam_cfg["bssids"]}

    networks = config.require("networks")
    primary = next(n for n in networks if n.get("ssid") == ssid)
    device.wifi.set_enabled(True)
    status = device.wifi.connect(
        ssid=ssid,
        security=primary.get("type", "open"),
        password=primary.get("password"),
    )
    starting_bssid = status.bssid.lower() if status.bssid else None
    log.info("Starting BSSID: %s", starting_bssid)

    timeout = float(roam_cfg.get("timeout", 60))
    deadline = time.time() + timeout
    while time.time() < deadline:
        current = device.wifi.status().bssid
        if current and current.lower() != starting_bssid and current.lower() in expected_bssids:
            log.info("Roamed from %s to %s", starting_bssid, current)
            return
        time.sleep(2.0)
    pytest.fail(f"No roam detected within {timeout}s; still on {starting_bssid}")
