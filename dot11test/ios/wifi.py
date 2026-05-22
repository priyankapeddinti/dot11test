"""WiFi control surface for a jailbroken iOS device.

iOS has no built-in CLI equivalent of `cmd wifi`. Status can be read from
`scutil`/`ifconfig` and a few other system facilities. Control (enable,
disable, scan, connect, forget) requires either:

  * a helper binary on the device that links MobileWiFi.framework, or
  * a third-party utility installed via Sileo/Cydia.

This class supports both: configure command templates under `ios.wifi_helper`
in the config and they'll be invoked over SSH. If a helper isn't configured,
control methods raise NotImplementedError and read-only methods still work.

Expected helper output formats (any reasonable helper can match these):

  status:   one line of `key=value` pairs, any subset of:
            ssid="My SSID" bssid=aa:bb:cc:dd:ee:ff rssi=-55 freq=5180 enabled=1 connected=1
  scan:     one network per line, whitespace-separated:
            <bssid> <freq_mhz> <rssi_dbm> <ssid>
  enable/disable/connect/disconnect/forget: exit 0 on success.
"""
from __future__ import annotations

import logging
import re
import shlex
import time

from ..types import ScanResult, WifiStatus
from .ssh import Ssh

log = logging.getLogger(__name__)


class IosWifi:
    """WiFi surface satisfying the same shape as android.wifi.Wifi."""

    def __init__(
        self,
        ssh: Ssh,
        interface: str = "en0",
        helper: dict | None = None,
    ):
        self.ssh = ssh
        self.interface = interface
        # helper: dict of action -> command template (str). Templates may use
        # {ssid}, {password}, {bssid}.
        self.helper = helper or {}

    # --- helpers ---------------------------------------------------------

    def _helper_cmd(self, action: str, **kw: str) -> str | None:
        tmpl = self.helper.get(action)
        if not tmpl:
            return None
        return tmpl.format(**{k: shlex.quote(str(v)) for k, v in kw.items()})

    def _require_helper(self, action: str, **kw: str) -> str:
        cmd = self._helper_cmd(action, **kw)
        if cmd is None:
            raise NotImplementedError(
                f"iOS WiFi {action!r} requires ios.wifi_helper.{action} in config "
                f"(no built-in CLI on iOS for this operation)."
            )
        return cmd

    # --- power / radio ---------------------------------------------------

    def set_enabled(self, enabled: bool) -> None:
        cmd = self._require_helper("enable" if enabled else "disable")
        self.ssh.shell(cmd)
        deadline = time.time() + 15
        while time.time() < deadline:
            if self.status().enabled == enabled:
                return
            time.sleep(0.5)
        raise TimeoutError(f"WiFi did not reach enabled={enabled} within 15s")

    # --- scan ------------------------------------------------------------

    def start_scan(self) -> None:
        cmd = self._helper_cmd("scan_start")
        if cmd:
            self.ssh.shell(cmd, check=False)

    def scan_results(self) -> list[ScanResult]:
        cmd = self._require_helper("scan")
        out = self.ssh.shell(cmd).stdout
        results: list[ScanResult] = []
        for line in out.splitlines():
            parts = line.split(None, 3)
            if len(parts) < 4 or not re.match(r"^[0-9a-f:]{17}$", parts[0], re.I):
                continue
            try:
                bssid = parts[0]
                freq = int(parts[1])
                rssi = int(parts[2])
            except ValueError:
                continue
            ssid = parts[3].strip().strip('"')
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
        if security.lower() not in {"open", "wpa2", "wpa3", "owe"}:
            raise ValueError(f"Unsupported security: {security}")
        if security.lower() != "open" and not password:
            raise ValueError(f"{security} network requires a password")
        cmd = self._require_helper(
            "connect", ssid=ssid, password=password or "", security=security
        )
        self.ssh.shell(cmd)
        return self.wait_for_connected(ssid=ssid, timeout=timeout)

    def disconnect(self) -> None:
        cmd = self._helper_cmd("disconnect")
        if cmd:
            self.ssh.shell(cmd, check=False)
        else:
            # Fallback: toggle radio if disable/enable are available.
            self.set_enabled(False)
            self.set_enabled(True)

    def forget(self, ssid: str) -> None:
        cmd = self._helper_cmd("forget", ssid=ssid)
        if cmd:
            self.ssh.shell(cmd, check=False)

    # --- status ----------------------------------------------------------

    def status(self) -> WifiStatus:
        ssid = bssid = None
        rssi = freq = None
        enabled = True   # assume on; only the helper can authoritatively answer
        connected = False
        ip = None

        # 1) Try a configured status helper for SSID/BSSID/RSSI/freq/enabled.
        cmd = self._helper_cmd("status")
        if cmd:
            out = self.ssh.shell(cmd, check=False).stdout
            ssid = self._kv(out, "ssid") or ssid
            bssid = self._kv(out, "bssid") or bssid
            rssi = self._kv_int(out, "rssi") or rssi
            freq = self._kv_int(out, "freq") or freq
            enabled_kv = self._kv(out, "enabled")
            if enabled_kv is not None:
                enabled = enabled_kv in ("1", "true", "yes")

        # 2) Always cross-check connectivity via ifconfig + route.
        ifc = self.ssh.shell(f"ifconfig {self.interface}", check=False).stdout
        m = re.search(r"inet\s+([0-9.]+)\b", ifc)
        if m:
            ip = m.group(1)
        up = "status: active" in ifc or "UP," in ifc
        connected = bool(ip) and up

        return WifiStatus(
            enabled=enabled,
            connected=connected,
            ssid=ssid,
            bssid=bssid,
            rssi_dbm=rssi,
            link_speed_mbps=None,
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
            if last.connected and last.ip_address and (ssid is None or last.ssid in (None, ssid)):
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

    # --- parsing ---------------------------------------------------------

    @staticmethod
    def _kv(text: str, key: str) -> str | None:
        # Match key="quoted value" or key=token
        m = re.search(rf'\b{re.escape(key)}=("([^"]*)"|(\S+))', text)
        if not m:
            return None
        return m.group(2) if m.group(2) is not None else m.group(3)

    @staticmethod
    def _kv_int(text: str, key: str) -> int | None:
        val = IosWifi._kv(text, key)
        try:
            return int(val) if val is not None else None
        except ValueError:
            return None
