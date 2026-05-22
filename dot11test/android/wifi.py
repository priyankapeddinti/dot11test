from __future__ import annotations

import logging
import re
import shlex
import time

from ..types import ScanResult, WifiStatus
from .adb import Adb

log = logging.getLogger(__name__)


class Wifi:
    """WiFi control surface backed by `cmd wifi` and dumpsys (Android 11+)."""

    def __init__(self, adb: Adb):
        self.adb = adb

    # --- power / radio ---------------------------------------------------

    def set_enabled(self, enabled: bool) -> None:
        state = "enable" if enabled else "disable"
        self.adb.shell(f"svc wifi {state}")
        # `svc wifi` returns immediately; poll until reflected.
        deadline = time.time() + 15
        while time.time() < deadline:
            if self.status().enabled == enabled:
                return
            time.sleep(0.5)
        raise TimeoutError(f"WiFi did not reach enabled={enabled} within 15s")

    # --- scan ------------------------------------------------------------

    def start_scan(self) -> None:
        self.adb.shell("cmd wifi start-scan")

    def scan_results(self) -> list[ScanResult]:
        out = self.adb.shell("cmd wifi list-scan-results").stdout
        results: list[ScanResult] = []
        # Format (Android 12+):
        # BSSID              Frequency  RSSI  Age(sec) SSID                              Flags
        # aa:bb:cc:dd:ee:ff   5180       -55    1.234   "MySSID"                          [WPA2-PSK-CCMP]
        for line in out.splitlines():
            parts = line.split()
            if len(parts) < 5 or not re.match(r"^[0-9a-f:]{17}$", parts[0], re.I):
                continue
            try:
                bssid = parts[0]
                freq = int(parts[1])
                rssi = int(parts[2])
            except ValueError:
                continue
            ssid_match = re.search(r'"([^"]*)"', line)
            ssid = ssid_match.group(1) if ssid_match else ""
            results.append(ScanResult(bssid=bssid, frequency_mhz=freq, rssi_dbm=rssi, ssid=ssid))
        return results

    def scan_and_wait(self, timeout: float = 15) -> list[ScanResult]:
        self.start_scan()
        deadline = time.time() + timeout
        last: list[ScanResult] = []
        while time.time() < deadline:
            last = self.scan_results()
            if last:
                return last
            time.sleep(1.0)
        return last

    # --- connect ---------------------------------------------------------

    def connect(
        self,
        ssid: str,
        security: str = "open",
        password: str | None = None,
        timeout: float = 30,
    ) -> WifiStatus:
        """Connect to a network via `cmd wifi connect-network`.

        security: 'open', 'wpa2', 'wpa3', 'owe'.
        """
        sec = security.lower()
        if sec == "open":
            cmd = f"cmd wifi connect-network {shlex.quote(ssid)} open"
        elif sec in {"wpa2", "wpa3"}:
            if not password:
                raise ValueError(f"{security} network requires a password")
            cmd = (
                f"cmd wifi connect-network {shlex.quote(ssid)} {sec} "
                f"{shlex.quote(password)}"
            )
        elif sec == "owe":
            cmd = f"cmd wifi connect-network {shlex.quote(ssid)} owe"
        else:
            raise ValueError(f"Unsupported security: {security}")
        self.adb.shell(cmd)
        return self.wait_for_connected(ssid=ssid, timeout=timeout)

    def disconnect(self) -> None:
        # Forget-then-disable is harsh; use `cmd wifi disconnect` if available,
        # otherwise toggle radio.
        res = self.adb.shell("cmd wifi disconnect", check=False)
        if not res.ok:
            self.set_enabled(False)
            self.set_enabled(True)

    def forget(self, ssid: str) -> None:
        self.adb.shell(f"cmd wifi forget-network {shlex.quote(ssid)}", check=False)

    # --- status ----------------------------------------------------------

    def status(self) -> WifiStatus:
        out = self.adb.shell("dumpsys wifi").stdout
        enabled = "Wi-Fi is enabled" in out or "Wi-Fi is connected" in out
        if "Wi-Fi is disabled" in out:
            enabled = False

        # Look for the "mWifiInfo" line or the "Wi-Fi is connected" block.
        ssid = self._extract(out, r'SSID:\s*"?([^",\n]+)"?')
        bssid = self._extract(out, r"BSSID:\s*([0-9a-fA-F:]{17})")
        rssi = self._extract_int(out, r"RSSI:\s*(-?\d+)")
        link = self._extract_int(out, r"Link speed:\s*(\d+)\s*Mbps")
        freq = self._extract_int(out, r"Frequency:\s*(\d+)\s*MHz")

        ip = None
        ip_match = re.search(r"inet addr:\s*([0-9.]+)|inet ([0-9.]+)", out)
        if ip_match:
            ip = ip_match.group(1) or ip_match.group(2)
        if ip is None:
            # Fallback to `ip addr show wlan0`.
            res = self.adb.shell("ip -4 addr show wlan0", check=False)
            m = re.search(r"inet\s+([0-9.]+)/", res.stdout)
            if m:
                ip = m.group(1)

        connected = ssid not in (None, "", "<unknown ssid>") and bssid is not None
        return WifiStatus(
            enabled=enabled,
            connected=connected,
            ssid=ssid,
            bssid=bssid,
            rssi_dbm=rssi,
            link_speed_mbps=link,
            frequency_mhz=freq,
            ip_address=ip,
        )

    def wait_for_connected(
        self, ssid: str | None = None, timeout: float = 30
    ) -> WifiStatus:
        deadline = time.time() + timeout
        last: WifiStatus | None = None
        while time.time() < deadline:
            last = self.status()
            if last.connected and last.ip_address and (ssid is None or last.ssid == ssid):
                return last
            time.sleep(1.0)
        raise TimeoutError(
            f"Did not connect to SSID={ssid!r} within {timeout}s; last status={last}"
        )

    def wait_for_disconnected(self, timeout: float = 15) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self.status().connected:
                return
            time.sleep(0.5)
        raise TimeoutError("WiFi did not disconnect in time")

    # --- helpers ---------------------------------------------------------

    @staticmethod
    def _extract(text: str, pattern: str) -> str | None:
        m = re.search(pattern, text)
        return m.group(1).strip() if m else None

    @staticmethod
    def _extract_int(text: str, pattern: str) -> int | None:
        m = re.search(pattern, text)
        try:
            return int(m.group(1)) if m else None
        except ValueError:
            return None
