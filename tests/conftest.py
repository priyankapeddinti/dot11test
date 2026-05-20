from __future__ import annotations

import logging
import os

import pytest

from dot11test.adb import Adb
from dot11test.config import Config, ConfigError, load_config
from dot11test.device import AndroidDevice

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def config() -> Config:
    try:
        return load_config()
    except ConfigError as e:
        pytest.skip(str(e))


@pytest.fixture(scope="session")
def adb(config: Config) -> Adb:
    serial = config.get("device", "serial") or os.environ.get("ANDROID_SERIAL")
    a = Adb(serial=serial)
    devices = a.devices()
    if not devices:
        pytest.skip("No adb devices attached")
    if serial is None and len(devices) > 1:
        pytest.skip(f"Multiple devices attached; set device.serial. Found: {devices}")
    if serial is None:
        a.serial = devices[0]
    a.root()
    return a


@pytest.fixture(scope="session")
def device(adb: Adb, config: Config) -> AndroidDevice:
    iperf_path = config.get("device", "iperf3_path", default="/data/local/tmp/iperf3")
    d = AndroidDevice(adb, iperf3_path=iperf_path)
    info = d.info()
    log.info("DUT: %s (Android %s, SDK %d, %s)", info.model, info.android_release, info.sdk, info.serial)
    d.screen_on()
    return d


@pytest.fixture
def wifi_on(device: AndroidDevice):
    """Ensure WiFi is enabled before the test; leave it enabled after."""
    device.wifi.set_enabled(True)
    yield device.wifi


@pytest.fixture
def connected(device: AndroidDevice, config: Config):
    """Connect to the first configured network and yield wifi status."""
    networks = config.require("networks")
    primary = next((n for n in networks if isinstance(n, dict) and "ssid" in n), None)
    if not primary:
        pytest.skip("No networks configured")
    device.wifi.set_enabled(True)
    status = device.wifi.connect(
        ssid=primary["ssid"],
        security=primary.get("type", "open"),
        password=primary.get("password"),
    )
    log.info("Connected: ssid=%s bssid=%s rssi=%s freq=%s ip=%s",
             status.ssid, status.bssid, status.rssi_dbm, status.frequency_mhz, status.ip_address)
    yield status
