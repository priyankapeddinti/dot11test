import logging
from dataclasses import asdict

import pytest

from dot11test.stats import record

log = logging.getLogger(__name__)
pytestmark = pytest.mark.performance


@pytest.fixture
def iperf_runner(device, config, connected):
    device.iperf.check_available()
    return device.iperf, {
        "server": config.require("iperf", "server"),
        "port": int(config.get("iperf", "port", default=5201)),
        "duration": int(config.get("iperf", "duration", default=10)),
        "parallel": int(config.get("iperf", "parallel_streams", default=1)),
    }


def test_tcp_downlink(iperf_runner, config):
    iperf, params = iperf_runner
    result = iperf.run(**params, reverse=True)
    log.info("TCP DL: %.2f Mbps (retx=%s)", result.throughput_mbps, result.retransmits)
    record("tcp_downlink", asdict(result))
    threshold = float(config.get("thresholds", "min_tcp_dl_mbps", default=0))
    assert result.throughput_mbps >= threshold, (
        f"TCP DL {result.throughput_mbps:.2f} Mbps below threshold {threshold} Mbps"
    )


def test_tcp_uplink(iperf_runner, config):
    iperf, params = iperf_runner
    result = iperf.run(**params, reverse=False)
    log.info("TCP UL: %.2f Mbps (retx=%s)", result.throughput_mbps, result.retransmits)
    record("tcp_uplink", asdict(result))
    threshold = float(config.get("thresholds", "min_tcp_ul_mbps", default=0))
    assert result.throughput_mbps >= threshold


def test_udp_downlink(iperf_runner, config):
    iperf, params = iperf_runner
    target_bw = config.get("iperf", "udp_bandwidth", default="200M")
    result = iperf.run(**params, udp=True, bandwidth=target_bw, reverse=True)
    log.info("UDP DL: %.2f Mbps loss=%.2f%% jitter=%.2fms",
             result.throughput_mbps, result.lost_percent or 0, result.jitter_ms or 0)
    record("udp_downlink", asdict(result))
    threshold = float(config.get("thresholds", "min_udp_dl_mbps", default=0))
    assert result.throughput_mbps >= threshold
