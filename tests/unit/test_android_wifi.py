import pytest

from dot11test.android.wifi import Wifi
from dot11test.types import ScanResult, ShellResult

pytestmark = pytest.mark.unit

SCAN_OUT = """\
    BSSID              Frequency      RSSI           Age(sec)     SSID                                 Flags
  aa:bb:cc:dd:ee:01       5180        -48    1.2       "TestAP-WPA2"                       [WPA2-PSK-CCMP][ESS]
  aa:bb:cc:dd:ee:02       2437        -67    3.4       "TestAP-Open"                       [ESS]
  aa:bb:cc:dd:ee:03       6115        -71    0.9       "My AP With Spaces"                 [RSN-SAE-CCMP][ESS]
  not-a-bssid             abc         xyz
"""

DUMPSYS_CONNECTED = """\
Wi-Fi is enabled
mLastBssid aa:bb:cc:dd:ee:01
mWifiInfo SSID: "TestAP-WPA2", BSSID: aa:bb:cc:dd:ee:01, MAC: 02:00:00:00:00:00, \
Supplicant state: COMPLETED, RSSI: -48, Link speed: 866Mbps, Frequency: 5180MHz
"""

# Realistic ordering in some sections of dumpsys: BSSID appears before SSID.
DUMPSYS_BSSID_FIRST = """\
Wi-Fi is enabled
mWifiInfo BSSID: aa:bb:cc:dd:ee:01, SSID: "TestAP-WPA2", RSSI: -50, \
Link speed: 433 Mbps, Frequency: 5180 MHz
"""

DUMPSYS_DISABLED = "Wi-Fi is disabled\n"


def test_scan_results_parsing(fake_shell):
    results = Wifi(fake_shell({"list-scan-results": SCAN_OUT})).scan_results()
    assert [r.ssid for r in results] == ["TestAP-WPA2", "TestAP-Open", "My AP With Spaces"]
    assert results[0] == ScanResult("aa:bb:cc:dd:ee:01", 5180, -48, "TestAP-WPA2")
    assert [r.band for r in results] == ["5GHz", "2.4GHz", "6GHz"]


def test_status_connected(fake_shell):
    sh = fake_shell({
        "dumpsys wifi": DUMPSYS_CONNECTED,
        "ip -4 addr": "    inet 192.168.1.42/24 brd 192.168.1.255 scope global wlan0\n",
    })
    s = Wifi(sh).status()
    assert s.enabled and s.connected
    assert s.ssid == "TestAP-WPA2"
    assert s.bssid == "aa:bb:cc:dd:ee:01"
    assert s.rssi_dbm == -48
    assert s.ip_address == "192.168.1.42"


def test_status_ssid_not_confused_with_bssid(fake_shell):
    s = Wifi(fake_shell({"dumpsys wifi": DUMPSYS_BSSID_FIRST})).status()
    assert s.ssid == "TestAP-WPA2"
    assert s.link_speed_mbps == 433
    assert s.frequency_mhz == 5180


def test_status_disabled(fake_shell):
    s = Wifi(fake_shell({"dumpsys wifi": DUMPSYS_DISABLED})).status()
    assert not s.enabled and not s.connected


@pytest.mark.parametrize(
    "security,password,expected",
    [
        ("open", None, "cmd wifi connect-network TestAP open"),
        ("wpa2", "pa ss", "cmd wifi connect-network TestAP wpa2 'pa ss'"),
        ("WPA3", "x;rm -rf /", "cmd wifi connect-network TestAP wpa3 'x;rm -rf /'"),
    ],
)
def test_connect_builds_quoted_command(fake_shell, monkeypatch, security, password, expected):
    sh = fake_shell()
    w = Wifi(sh)
    monkeypatch.setattr(w, "wait_for_connected", lambda **kw: None)
    w.connect("TestAP", security, password)
    assert sh.calls[0] == expected


def test_connect_validation(fake_shell):
    w = Wifi(fake_shell())
    with pytest.raises(ValueError, match="requires a password"):
        w.connect("x", "wpa2")
    with pytest.raises(ValueError, match="Unsupported"):
        w.connect("x", "wep")


def test_wait_for_connected_times_out(fake_shell):
    w = Wifi(fake_shell({"dumpsys wifi": DUMPSYS_DISABLED}))
    with pytest.raises(TimeoutError):
        w.wait_for_connected(timeout=0.01)


def _spy_toggles(w, monkeypatch):
    toggles = []
    monkeypatch.setattr(w, "set_enabled", toggles.append)
    return toggles


def test_disconnect_unsupported_command_toggles_radio(fake_shell, monkeypatch):
    w = Wifi(fake_shell({"cmd wifi disconnect": ShellResult(255, "", "Unknown command")}))
    toggles = _spy_toggles(w, monkeypatch)
    w.disconnect()
    assert toggles == [False, True]


def test_disconnect_observed_does_not_toggle(fake_shell, monkeypatch):
    w = Wifi(fake_shell({"dumpsys wifi": DUMPSYS_DISABLED}))
    toggles = _spy_toggles(w, monkeypatch)
    w.disconnect()
    assert toggles == []


def test_disconnect_fast_rejoin_falls_back_to_toggle(fake_shell, monkeypatch):
    # Device still reports connected (auto-rejoin beat our poll).
    w = Wifi(fake_shell({"dumpsys wifi": DUMPSYS_CONNECTED}))
    toggles = _spy_toggles(w, monkeypatch)
    w.disconnect(timeout=0.01)
    assert toggles == [False, True]
