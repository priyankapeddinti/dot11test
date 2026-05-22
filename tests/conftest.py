from __future__ import annotations

import logging
import os

import pytest

from dot11test.config import Config, ConfigError, load_config

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def config() -> Config:
    try:
        return load_config()
    except ConfigError as e:
        pytest.skip(str(e))


@pytest.fixture(scope="session")
def platform(config: Config) -> str:
    p = (os.environ.get("DOT11_PLATFORM") or config.get("platform", default="android")).lower()
    if p not in {"android", "ios"}:
        pytest.fail(f"Unknown platform: {p!r} (expected 'android' or 'ios')")
    return p


@pytest.fixture(scope="session")
def device(config: Config, platform: str):
    if platform == "android":
        return _make_android_device(config)
    return _make_ios_device(config)


def _make_android_device(config: Config):
    from dot11test.android import Adb, AndroidDevice

    serial = config.get("device", "serial") or os.environ.get("ANDROID_SERIAL")
    adb = Adb(serial=serial)
    devices = adb.devices()
    if not devices:
        pytest.skip("No adb devices attached")
    if serial is None and len(devices) > 1:
        pytest.skip(f"Multiple devices attached; set device.serial. Found: {devices}")
    if serial is None:
        adb.serial = devices[0]
    adb.root()
    iperf_path = config.get("device", "iperf3_path", default="/data/local/tmp/iperf3")
    d = AndroidDevice(adb, iperf3_path=iperf_path)
    info = d.info()
    log.info(
        "DUT(android): %s (Android %s, SDK %d, %s)",
        info.model, info.android_release, info.sdk, info.serial,
    )
    d.screen_on()
    return d


def _make_ios_device(config: Config):
    from dot11test.ios import IosDevice, Ssh

    ios_cfg = config.require("ios")
    ssh = Ssh(
        host=ios_cfg.get("host", "127.0.0.1"),
        port=int(ios_cfg.get("port", 2222)),
        user=ios_cfg.get("user", "root"),
        key_path=ios_cfg.get("ssh_key"),
        password=ios_cfg.get("password"),
    )
    if not ssh.reachable():
        pytest.skip(
            f"iOS device not reachable at {ssh.user}@{ssh.host}:{ssh.port}. "
            f"Run `iproxy {ssh.port} 22 <udid>` and verify SSH credentials."
        )
    d = IosDevice(
        ssh,
        iperf3_path=ios_cfg.get("iperf3_path", "/usr/local/bin/iperf3"),
        interface=ios_cfg.get("interface", "en0"),
        wifi_helper=ios_cfg.get("wifi_helper") or {},
    )
    info = d.info()
    log.info(
        "DUT(ios): %s (iOS %s build %s, %s)",
        info.product, info.ios_version, info.build, info.host,
    )
    return d


@pytest.fixture
def wifi_on(device):
    """Ensure WiFi is enabled before the test."""
    try:
        device.wifi.set_enabled(True)
    except NotImplementedError as e:
        pytest.skip(str(e))
    yield device.wifi


@pytest.fixture
def connected(device, config):
    """Connect to the first configured network and yield wifi status."""
    networks = config.require("networks")
    primary = next((n for n in networks if isinstance(n, dict) and "ssid" in n), None)
    if not primary:
        pytest.skip("No networks configured")
    try:
        device.wifi.set_enabled(True)
        status = device.wifi.connect(
            ssid=primary["ssid"],
            security=primary.get("type", "open"),
            password=primary.get("password"),
        )
    except NotImplementedError as e:
        pytest.skip(str(e))
    log.info(
        "Connected: ssid=%s bssid=%s rssi=%s freq=%s ip=%s",
        status.ssid, status.bssid, status.rssi_dbm, status.frequency_mhz, status.ip_address,
    )
    yield status
