import logging
from dataclasses import asdict

import pytest

from dot11test.ping import ping
from dot11test.stats import record

log = logging.getLogger(__name__)
pytestmark = pytest.mark.performance


def test_ping_latency(device, config, connected):
    target = config.require("ping", "target")
    count = int(config.get("ping", "count", default=50))
    interval = float(config.get("ping", "interval", default=0.2))
    result = ping(device.adb, target, count=count, interval=interval)
    log.info(
        "ping %s: tx=%d rx=%d loss=%.2f%% avg=%.2fms mdev=%.2fms",
        target, result.transmitted, result.received, result.loss_percent,
        result.avg_ms or 0, result.mdev_ms or 0,
    )
    record("ping", asdict(result))

    max_avg = float(config.get("thresholds", "max_ping_avg_ms", default=100))
    max_loss = float(config.get("thresholds", "max_ping_loss_pct", default=5))
    assert result.received > 0, "No replies received"
    assert result.avg_ms is not None and result.avg_ms <= max_avg, (
        f"avg ping {result.avg_ms}ms exceeds {max_avg}ms"
    )
    assert result.loss_percent <= max_loss, (
        f"packet loss {result.loss_percent}% exceeds {max_loss}%"
    )
