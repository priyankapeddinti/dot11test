import pytest

from dot11test.ios.wifi import IosWifi

pytestmark = pytest.mark.unit

IFCONFIG_UP = """\
en0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
\tether 11:22:33:44:55:66
\tinet 192.168.1.77 netmask 0xffffff00 broadcast 192.168.1.255
\tstatus: active
"""

IFCONFIG_NO_IP = """\
en0: flags=8822<BROADCAST,SMART,SIMPLEX,MULTICAST> mtu 1500
\tstatus: inactive
"""

HELPER = {
    "status": "wifi-tool status",
    "scan": "wifi-tool scan",
    "connect": "wifi-tool connect {ssid} {password}",
    "enable": "wifi-tool on",
    "disable": "wifi-tool off",
}


def test_status_from_helper_and_ifconfig(fake_shell):
    sh = fake_shell({
        "wifi-tool status": 'ssid="My Home" bssid=aa:bb:cc:dd:ee:ff rssi=-55 freq=5180 enabled=1',
        "ifconfig": IFCONFIG_UP,
    })
    s = IosWifi(sh, helper=HELPER).status()
    assert s.connected and s.enabled
    assert (s.ssid, s.bssid, s.rssi_dbm, s.frequency_mhz) == ("My Home", "aa:bb:cc:dd:ee:ff", -55, 5180)
    assert s.ip_address == "192.168.1.77"


def test_status_without_helper_uses_ifconfig_only(fake_shell):
    s = IosWifi(fake_shell({"ifconfig": IFCONFIG_NO_IP})).status()
    assert not s.connected
    assert s.ssid is None and s.ip_address is None


def test_status_enabled_zero(fake_shell):
    sh = fake_shell({"wifi-tool status": "enabled=0", "ifconfig": IFCONFIG_NO_IP})
    assert IosWifi(sh, helper=HELPER).status().enabled is False


def test_scan_parsing(fake_shell):
    out = (
        "aa:bb:cc:dd:ee:01 5180 -48 TestAP-WPA2\n"
        'aa:bb:cc:dd:ee:02 2412 -70 "Cafe Guest WiFi"\n'
        "garbage line\n"
    )
    results = IosWifi(fake_shell({"wifi-tool scan": out}), helper=HELPER).scan_results()
    assert [(r.ssid, r.band) for r in results] == [("TestAP-WPA2", "5GHz"), ("Cafe Guest WiFi", "2.4GHz")]


def test_connect_quotes_template_args(fake_shell, monkeypatch):
    sh = fake_shell()
    w = IosWifi(sh, helper=HELPER)
    monkeypatch.setattr(w, "wait_for_connected", lambda **kw: None)
    w.connect("Net; reboot", "wpa2", "p'w")
    assert sh.calls[0] == "wifi-tool connect 'Net; reboot' 'p'\"'\"'w'"


def test_missing_helper_raises_not_implemented(fake_shell):
    w = IosWifi(fake_shell(), helper={})
    for call in (lambda: w.set_enabled(True), w.scan_results, lambda: w.connect("x")):
        with pytest.raises(NotImplementedError, match="wifi_helper"):
            call()


def test_wait_for_connected_rejects_wrong_ssid(fake_shell):
    sh = fake_shell({"wifi-tool status": 'ssid="Other"', "ifconfig": IFCONFIG_UP})
    with pytest.raises(TimeoutError):
        IosWifi(sh, helper=HELPER).wait_for_connected(ssid="Mine", timeout=0.01)


def test_wait_for_connected_rejects_missing_ssid_when_status_helper_exists(fake_shell):
    # Helper is configured but didn't report an SSID: don't treat that as a match.
    sh = fake_shell({"wifi-tool status": "rssi=-50", "ifconfig": IFCONFIG_UP})
    with pytest.raises(TimeoutError):
        IosWifi(sh, helper=HELPER).wait_for_connected(ssid="Mine", timeout=0.01)


def test_wait_for_connected_accepts_unknown_ssid_without_status_helper(fake_shell, caplog):
    helper = {k: v for k, v in HELPER.items() if k != "status"}
    w = IosWifi(fake_shell({"ifconfig": IFCONFIG_UP}), helper=helper)
    assert w.wait_for_connected(ssid="Mine", timeout=1).connected
    assert "Cannot verify SSID" in caplog.text


class SequenceShell:
    """Returns ifconfig output that changes after the disable command runs."""

    def __init__(self):
        self.calls, self.radio_on = [], True

    def shell(self, cmd, **kw):
        from dot11test.types import ShellResult
        self.calls.append(cmd)
        if cmd == "wifi-tool off":
            self.radio_on = False
        elif cmd == "wifi-tool on":
            self.radio_on = True
        if cmd.startswith("ifconfig"):
            return ShellResult(0, IFCONFIG_UP if self.radio_on else IFCONFIG_NO_IP, "")
        return ShellResult(0, "", "")


def test_set_enabled_without_enabled_report_uses_connectivity_proxy():
    helper = {k: v for k, v in HELPER.items() if k != "status"}
    w = IosWifi(SequenceShell(), helper=helper)
    w.set_enabled(False)  # returns once not connected, instead of timing out
    assert w.status().enabled is False
    w.set_enabled(True)
    assert w.status().enabled is True


def test_set_enabled_prefers_helper_enabled_report(fake_shell):
    sh = fake_shell({"wifi-tool status": "enabled=1", "ifconfig": IFCONFIG_NO_IP})
    w = IosWifi(sh, helper=HELPER)
    w.set_enabled(True)
    assert w.status().enabled is True


def test_disconnect_helper_observed(fake_shell, monkeypatch):
    helper = {**HELPER, "disconnect": "wifi-tool disconnect"}
    w = IosWifi(fake_shell({"ifconfig": IFCONFIG_NO_IP}), helper=helper)
    toggles = []
    monkeypatch.setattr(w, "set_enabled", toggles.append)
    w.disconnect()
    assert toggles == []


def test_disconnect_fast_rejoin_toggles(fake_shell, monkeypatch):
    helper = {**HELPER, "disconnect": "wifi-tool disconnect"}
    w = IosWifi(fake_shell({"ifconfig": IFCONFIG_UP}), helper=helper)
    toggles = []
    monkeypatch.setattr(w, "set_enabled", toggles.append)
    w.disconnect(timeout=0.01)
    assert toggles == [False, True]
