from __future__ import annotations

import logging
import shlex
import subprocess

from ..types import ShellResult

log = logging.getLogger(__name__)


class AdbError(RuntimeError):
    def __init__(self, cmd: list[str], returncode: int, stdout: str, stderr: str):
        super().__init__(
            f"adb {' '.join(shlex.quote(c) for c in cmd)} exited {returncode}\n"
            f"stdout: {stdout.strip()}\nstderr: {stderr.strip()}"
        )
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class Adb:
    """Thin adb wrapper bound to a single device serial."""

    def __init__(self, serial: str | None = None, adb_binary: str = "adb"):
        self.serial = serial
        self.adb_binary = adb_binary

    def _prefix(self) -> list[str]:
        if self.serial:
            return [self.adb_binary, "-s", self.serial]
        return [self.adb_binary]

    def run(
        self,
        args: list[str],
        *,
        timeout: float | None = 60,
        check: bool = True,
        input_text: str | None = None,
    ) -> ShellResult:
        cmd = self._prefix() + args
        log.debug("adb cmd: %s", " ".join(shlex.quote(c) for c in cmd))
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=input_text,
        )
        result = ShellResult(proc.returncode, proc.stdout, proc.stderr)
        if check and not result.ok:
            raise AdbError(cmd, result.returncode, result.stdout, result.stderr)
        return result

    def shell(
        self,
        cmd: str,
        *,
        timeout: float | None = 60,
        check: bool = True,
        as_root: bool = False,
    ) -> ShellResult:
        if as_root:
            cmd = f"su -c {shlex.quote(cmd)}"
        return self.run(["shell", cmd], timeout=timeout, check=check)

    def push(self, local: str, remote: str) -> None:
        self.run(["push", local, remote])

    def pull(self, remote: str, local: str) -> None:
        self.run(["pull", remote, local])

    def wait_for_device(self, timeout: float = 60) -> None:
        self.run(["wait-for-device"], timeout=timeout)

    def root(self) -> None:
        """Restart adbd as root (userdebug/eng builds only). No-op on user builds."""
        try:
            self.run(["root"], timeout=15, check=False)
            self.wait_for_device()
        except Exception as e:
            log.warning("adb root failed (likely user build): %s", e)

    def devices(self) -> list[str]:
        out = self.run(["devices"], timeout=10).stdout
        serials: list[str] = []
        for line in out.splitlines()[1:]:
            line = line.strip()
            if line and "\tdevice" in line:
                serials.append(line.split("\t", 1)[0])
        return serials
