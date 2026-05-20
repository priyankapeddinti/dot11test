from __future__ import annotations

import logging
from dataclasses import dataclass

from .adb import Adb
from .iperf import Iperf3
from .wifi import Wifi

log = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    serial: str
    model: str
    android_release: str
    sdk: int
    build: str


class AndroidDevice:
    """High-level handle to a single Android device under test."""

    def __init__(self, adb: Adb, iperf3_path: str = "/data/local/tmp/iperf3"):
        self.adb = adb
        self.wifi = Wifi(adb)
        self.iperf = Iperf3(adb, binary_path=iperf3_path)

    @property
    def serial(self) -> str:
        return self.adb.serial or "(default)"

    def info(self) -> DeviceInfo:
        def prop(name: str) -> str:
            return self.adb.shell(f"getprop {name}").stdout.strip()

        sdk_str = prop("ro.build.version.sdk")
        try:
            sdk = int(sdk_str)
        except ValueError:
            sdk = 0
        return DeviceInfo(
            serial=self.serial,
            model=prop("ro.product.model"),
            android_release=prop("ro.build.version.release"),
            sdk=sdk,
            build=prop("ro.build.display.id"),
        )

    def screen_on(self) -> None:
        """Ensure screen is on and unlocked (best-effort)."""
        # 224 = KEYCODE_WAKEUP, 82 = KEYCODE_MENU (dismisses simple lockscreen).
        self.adb.shell("input keyevent 224", check=False)
        self.adb.shell("input keyevent 82", check=False)

    def airplane_mode(self, enabled: bool) -> None:
        val = "1" if enabled else "0"
        self.adb.shell(f"settings put global airplane_mode_on {val}", as_root=True, check=False)
        self.adb.shell(
            f"am broadcast -a android.intent.action.AIRPLANE_MODE --ez state {str(enabled).lower()}",
            as_root=True,
            check=False,
        )
