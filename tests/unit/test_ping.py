import pytest

from dot11test.ping import ping

pytestmark = pytest.mark.unit

ANDROID_OK = """\
PING 192.168.1.1 (192.168.1.1) 56(84) bytes of data.
64 bytes from 192.168.1.1: icmp_seq=1 ttl=64 time=3.12 ms

--- 192.168.1.1 ping statistics ---
50 packets transmitted, 49 received, 2% packet loss, time 9812ms
rtt min/avg/max/mdev = 1.234/3.456/9.876/1.111 ms
"""

IOS_OK = """\
PING 192.168.1.1 (192.168.1.1): 56 data bytes

--- 192.168.1.1 ping statistics ---
10 packets transmitted, 10 packets received, 0.0% packet loss
round-trip min/avg/max/stddev = 2.001/4.500/8.250/1.750 ms
"""

ALL_LOST = """\
--- 10.0.0.99 ping statistics ---
5 packets transmitted, 0 received, 100% packet loss, time 4000ms
"""


def test_parses_android_output(fake_shell):
    r = ping(fake_shell({"ping": ANDROID_OK}), "192.168.1.1", count=50)
    assert (r.transmitted, r.received, r.loss_percent) == (50, 49, 2.0)
    assert (r.min_ms, r.avg_ms, r.max_ms, r.mdev_ms) == (1.234, 3.456, 9.876, 1.111)
    assert r.jitter_ms == 1.111


def test_parses_ios_output(fake_shell):
    r = ping(fake_shell({"ping": IOS_OK}), "192.168.1.1", count=10)
    assert (r.transmitted, r.loss_percent, r.avg_ms, r.mdev_ms) == (10, 0.0, 4.5, 1.75)


def test_total_loss_has_no_rtt(fake_shell):
    r = ping(fake_shell({"ping": ALL_LOST}), "10.0.0.99", count=5)
    assert r.received == 0
    assert r.loss_percent == 100.0
    assert r.avg_ms is None


def test_unparseable_output_defaults_to_full_loss(fake_shell):
    r = ping(fake_shell({"ping": "ping: unknown host"}), "nope")
    assert r.transmitted == 0 and r.loss_percent == 100.0


def test_builds_command(fake_shell):
    sh = fake_shell()
    ping(sh, "1.2.3.4", count=7, interval=0.5, packet_size=1400)
    assert sh.calls == ["ping -c 7 -i 0.5 -s 1400 1.2.3.4"]
