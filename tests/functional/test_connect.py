import logging

import pytest

log = logging.getLogger(__name__)
pytestmark = pytest.mark.functional


@pytest.mark.parametrize("net_index", [0])
def test_connect_to_configured_network(device, config, net_index):
    networks = config.require("networks")
    targets = [n for n in networks if isinstance(n, dict) and "ssid" in n]
    if net_index >= len(targets):
        pytest.skip("network index out of range")
    net = targets[net_index]
    device.wifi.set_enabled(True)
    status = device.wifi.connect(
        ssid=net["ssid"],
        security=net.get("type", "open"),
        password=net.get("password"),
    )
    assert status.connected
    assert status.ssid == net["ssid"]
    assert status.ip_address, "No IP address assigned"


def test_disconnect_reconnect(connected, device):
    original_ssid = connected.ssid
    device.wifi.disconnect()
    device.wifi.wait_for_disconnected(timeout=15)
    status = device.wifi.wait_for_connected(ssid=original_ssid, timeout=30)
    assert status.connected and status.ssid == original_ssid
