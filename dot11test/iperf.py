from __future__ import annotations

import json
import logging
import shlex
from dataclasses import dataclass

from .shell import Shell

log = logging.getLogger(__name__)


@dataclass
class IperfResult:
    protocol: str           # 'tcp' or 'udp'
    direction: str          # 'downlink' (server->client) or 'uplink' (client->server)
    throughput_mbps: float
    retransmits: int | None
    jitter_ms: float | None
    lost_packets: int | None
    lost_percent: float | None
    raw: dict


class Iperf3:
    """Run iperf3 on the device against a host server. Works for any Shell."""

    def __init__(self, shell: Shell, binary_path: str = "/data/local/tmp/iperf3"):
        self.shell = shell
        self.binary = binary_path

    def check_available(self) -> None:
        res = self.shell.shell(
            f"test -x {shlex.quote(self.binary)} && echo OK", check=False
        )
        if "OK" not in res.stdout:
            raise RuntimeError(
                f"iperf3 binary not found or not executable at {self.binary} on device. "
                f"Install it on the DUT and set device.iperf3_path in config."
            )

    def run(
        self,
        server: str,
        *,
        port: int = 5201,
        duration: int = 10,
        parallel: int = 1,
        udp: bool = False,
        bandwidth: str | None = None,
        reverse: bool = False,
        timeout: float | None = None,
    ) -> IperfResult:
        protocol = "udp" if udp else "tcp"
        direction = "downlink" if reverse else "uplink"
        args = [
            self.binary,
            "-c", server,
            "-p", str(port),
            "-t", str(duration),
            "-P", str(parallel),
            "-J",
            "--connect-timeout", "5000",
        ]
        if udp:
            args.append("-u")
            if bandwidth:
                args += ["-b", bandwidth]
        if reverse:
            args.append("-R")

        cmd = " ".join(shlex.quote(a) for a in args)
        log.info("iperf3 %s %s: %s", protocol, direction, cmd)
        res = self.shell.shell(cmd, timeout=timeout or (duration + 30))
        try:
            data = json.loads(res.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"iperf3 did not return JSON: {e}\n{res.stdout[:500]}")

        end = data.get("end", {})
        if udp:
            summary = end.get("sum", {})
            throughput = summary.get("bits_per_second", 0) / 1e6
            return IperfResult(
                protocol="udp",
                direction=direction,
                throughput_mbps=throughput,
                retransmits=None,
                jitter_ms=summary.get("jitter_ms"),
                lost_packets=summary.get("lost_packets"),
                lost_percent=summary.get("lost_percent"),
                raw=data,
            )

        sum_key = "sum_received" if reverse else "sum_sent"
        summary = end.get(sum_key) or end.get("sum_sent", {})
        throughput = summary.get("bits_per_second", 0) / 1e6
        retx = end.get("sum_sent", {}).get("retransmits")
        return IperfResult(
            protocol="tcp",
            direction=direction,
            throughput_mbps=throughput,
            retransmits=retx,
            jitter_ms=None,
            lost_packets=None,
            lost_percent=None,
            raw=data,
        )
