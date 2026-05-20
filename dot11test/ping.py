from __future__ import annotations

import re
from dataclasses import dataclass

from .adb import Adb


@dataclass
class PingResult:
    target: str
    transmitted: int
    received: int
    loss_percent: float
    min_ms: float | None
    avg_ms: float | None
    max_ms: float | None
    mdev_ms: float | None
    raw: str

    @property
    def jitter_ms(self) -> float | None:
        return self.mdev_ms


def ping(
    adb: Adb,
    target: str,
    *,
    count: int = 50,
    interval: float = 0.2,
    timeout: float | None = None,
    packet_size: int | None = None,
) -> PingResult:
    cmd = ["ping", "-c", str(count), "-i", str(interval)]
    if packet_size is not None:
        cmd += ["-s", str(packet_size)]
    cmd.append(target)
    res = adb.shell(" ".join(cmd), timeout=timeout or (count * interval + 30), check=False)
    out = res.stdout

    tx_rx = re.search(r"(\d+)\s+packets transmitted,\s*(\d+)\s+received", out)
    loss = re.search(r"(\d+(?:\.\d+)?)% packet loss", out)
    stats = re.search(
        r"(?:rtt|round-trip)\s+min/avg/max/(?:mdev|stddev)\s*=\s*"
        r"([0-9.]+)/([0-9.]+)/([0-9.]+)/([0-9.]+)\s*ms",
        out,
    )

    return PingResult(
        target=target,
        transmitted=int(tx_rx.group(1)) if tx_rx else 0,
        received=int(tx_rx.group(2)) if tx_rx else 0,
        loss_percent=float(loss.group(1)) if loss else 100.0,
        min_ms=float(stats.group(1)) if stats else None,
        avg_ms=float(stats.group(2)) if stats else None,
        max_ms=float(stats.group(3)) if stats else None,
        mdev_ms=float(stats.group(4)) if stats else None,
        raw=out,
    )
