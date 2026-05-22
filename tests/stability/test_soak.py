import logging
import os
import time

import pytest

from dot11test.ping import ping
from dot11test.stats import record

log = logging.getLogger(__name__)
pytestmark = [pytest.mark.stability, pytest.mark.soak]


def _soak_seconds(config) -> int:
    env = os.environ.get("DOT11_SOAK_SECONDS")
    if env:
        return int(env)
    return int(config.get("soak", "duration", default=300))


@pytest.mark.timeout(0)
def test_reconnect_loop(device, config):
    """Disconnect/reconnect N times; fail if any iteration cannot reconnect."""
    networks = config.require("networks")
    net = next(n for n in networks if isinstance(n, dict) and "ssid" in n)
    iterations = int(config.get("soak", "reconnect_iterations", default=20))

    device.wifi.set_enabled(True)
    failures: list[tuple[int, str]] = []
    for i in range(iterations):
        try:
            status = device.wifi.connect(
                ssid=net["ssid"],
                security=net.get("type", "open"),
                password=net.get("password"),
            )
            assert status.connected and status.ip_address
            device.wifi.disconnect()
            device.wifi.wait_for_disconnected(timeout=15)
            log.info("iter %d/%d ok", i + 1, iterations)
        except Exception as e:
            log.error("iter %d failed: %s", i + 1, e)
            failures.append((i + 1, str(e)))

    record("reconnect_loop", {"iterations": iterations, "failures": failures})
    assert not failures, f"{len(failures)}/{iterations} reconnect iterations failed"


@pytest.mark.timeout(0)
def test_ping_soak(device, config, connected):
    """Run continuous pings for the configured duration; track loss and outages."""
    target = config.require("ping", "target")
    duration = _soak_seconds(config)
    sample_interval = 30  # seconds between ping batches
    batch_count = 50
    batch_interval = 0.2

    log.info("Soak %ds, ping target=%s, batch every %ds", duration, target, sample_interval)
    deadline = time.time() + duration
    samples: list[dict] = []
    outages = 0

    while time.time() < deadline:
        result = ping(device.shell, target, count=batch_count, interval=batch_interval)
        sample = {
            "t": int(time.time()),
            "loss_pct": result.loss_percent,
            "avg_ms": result.avg_ms,
            "rssi": device.wifi.status().rssi_dbm,
        }
        samples.append(sample)
        if result.received == 0:
            outages += 1
            log.warning("outage at t=%d", sample["t"])
        else:
            log.info("loss=%.1f%% avg=%.2fms rssi=%s",
                     result.loss_percent, result.avg_ms or 0, sample["rssi"])
        time.sleep(max(0, sample_interval - batch_count * batch_interval))

    record("ping_soak", {"duration_s": duration, "outages": outages, "samples": samples})
    max_loss = float(config.get("thresholds", "max_ping_loss_pct", default=5))
    avg_loss = sum(s["loss_pct"] for s in samples) / max(len(samples), 1)
    assert outages == 0, f"{outages} full ping outages during soak"
    assert avg_loss <= max_loss, f"avg loss {avg_loss:.2f}% over soak exceeds {max_loss}%"
