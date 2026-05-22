"""Shared types used by all platform drivers."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ShellResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass
class ScanResult:
    bssid: str
    frequency_mhz: int
    rssi_dbm: int
    ssid: str

    @property
    def band(self) -> str:
        if 2400 <= self.frequency_mhz <= 2500:
            return "2.4GHz"
        if 5100 <= self.frequency_mhz <= 5900:
            return "5GHz"
        if 5925 <= self.frequency_mhz <= 7125:
            return "6GHz"
        return "unknown"


@dataclass
class WifiStatus:
    enabled: bool
    connected: bool
    ssid: str | None
    bssid: str | None
    rssi_dbm: int | None
    link_speed_mbps: int | None
    frequency_mhz: int | None
    ip_address: str | None
