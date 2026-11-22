from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from ..iperf import Iperf3
from .ssh import Ssh
from .wifi import IosWifi

log = logging.getLogger(__name__)


@dataclass
class IosDeviceInfo:
    host: str
    product: str           # e.g. "iPhone14,5"
    ios_version: str
    build: str


class IosDevice:
    """High-level handle to a jailbroken iOS device under test."""

    def __init__(
        self,
        ssh: Ssh,
        iperf3_path: str = "/usr/local/bin/iperf3",
        interface: str = "en0",
        wifi_helper: dict | None = None,
    ):
        self.ssh = ssh
        self.shell = ssh  # cross-platform alias; satisfies Shell protocol
        self.wifi = IosWifi(ssh, interface=interface, helper=wifi_helper)
        self.iperf = Iperf3(ssh, binary_path=iperf3_path)

    @property
    def serial(self) -> str:
        return f"{self.ssh.user}@{self.ssh.host}:{self.ssh.port}"

    def info(self) -> IosDeviceInfo:
        product = self.ssh.shell("uname -m", check=False).stdout.strip()
        # `sw_vers` is the most portable across jailbreaks.
        sw = self.ssh.shell("sw_vers", check=False).stdout
        ver = re.search(r"ProductVersion:\s*(\S+)", sw)
        build = re.search(r"BuildVersion:\s*(\S+)", sw)
        return IosDeviceInfo(
            host=f"{self.ssh.host}:{self.ssh.port}",
            product=product,
            ios_version=ver.group(1) if ver else "",
            build=build.group(1) if build else "",
        )

    def screen_on(self) -> None:
        # No-op on iOS; left for cross-platform fixture parity.
        pass

    def airplane_mode(self, enabled: bool) -> None:
        cmd_key = "airplane_on" if enabled else "airplane_off"
        tmpl = self.wifi.helper.get(cmd_key)
        if not tmpl:
            raise NotImplementedError(
                f"ios.wifi_helper.{cmd_key} not configured"
            )
        self.ssh.shell(tmpl)
