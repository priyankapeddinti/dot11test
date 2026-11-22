import json

import pytest

from dot11test.iperf import Iperf3
from dot11test.types import ShellResult

pytestmark = pytest.mark.unit

TCP_JSON = json.dumps({
    "end": {
        "sum_sent": {"bits_per_second": 120e6, "retransmits": 7},
        "sum_received": {"bits_per_second": 95e6},
    }
})

UDP_JSON = json.dumps({
    "end": {
        "sum": {
            "bits_per_second": 80e6,
            "jitter_ms": 0.42,
            "lost_packets": 12,
            "lost_percent": 0.5,
        }
    }
})


def test_tcp_downlink_uses_receiver_side(fake_shell):
    r = Iperf3(fake_shell({"iperf3": TCP_JSON})).run("srv", reverse=True)
    assert r.protocol == "tcp" and r.direction == "downlink"
    assert r.throughput_mbps == pytest.approx(95.0)
    assert r.retransmits == 7


def test_tcp_uplink_uses_receiver_side(fake_shell):
    # Receiver-measured throughput is the authoritative number in both directions.
    r = Iperf3(fake_shell({"iperf3": TCP_JSON})).run("srv", reverse=False)
    assert r.direction == "uplink"
    assert r.throughput_mbps == pytest.approx(95.0)


def test_udp_fields(fake_shell):
    r = Iperf3(fake_shell({"iperf3": UDP_JSON})).run("srv", udp=True, bandwidth="100M")
    assert r.protocol == "udp"
    assert r.throughput_mbps == pytest.approx(80.0)
    assert (r.jitter_ms, r.lost_packets, r.lost_percent) == (0.42, 12, 0.5)


def test_command_flags(fake_shell):
    sh = fake_shell({"iperf3": UDP_JSON})
    Iperf3(sh, binary_path="/bin/iperf3").run(
        "10.0.0.5", port=5202, duration=3, parallel=4, udp=True, bandwidth="50M", reverse=True
    )
    cmd = sh.calls[0].split()
    assert cmd[0] == "/bin/iperf3"
    for flag, val in [("-c", "10.0.0.5"), ("-p", "5202"), ("-t", "3"), ("-P", "4"), ("-b", "50M")]:
        assert cmd[cmd.index(flag) + 1] == val
    assert {"-u", "-R", "-J"} <= set(cmd)


def test_non_json_output_raises(fake_shell):
    with pytest.raises(RuntimeError, match="did not return JSON"):
        Iperf3(fake_shell({"iperf3": "iperf3: error"})).run("srv")


def test_check_available(fake_shell):
    Iperf3(fake_shell({"test -x": "OK\n"})).check_available()
    with pytest.raises(RuntimeError, match="not found"):
        Iperf3(fake_shell({"test -x": ShellResult(1, "", "")})).check_available()
