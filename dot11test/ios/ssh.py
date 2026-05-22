"""SSH driver for a jailbroken iOS device, tunneled over USB by iproxy.

Typical setup:

    # On the host, in another terminal:
    iproxy 2222 22 <udid>

Then point this at 127.0.0.1:2222 with root@ and your SSH key (or password
via sshpass). Default jailbreak password is `alpine`; change it.
"""
from __future__ import annotations

import logging
import shlex
import subprocess

from ..types import ShellResult

log = logging.getLogger(__name__)


class SshError(RuntimeError):
    def __init__(self, cmd: list[str], returncode: int, stdout: str, stderr: str):
        super().__init__(
            f"ssh {' '.join(shlex.quote(c) for c in cmd)} exited {returncode}\n"
            f"stdout: {stdout.strip()}\nstderr: {stderr.strip()}"
        )
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class Ssh:
    """SSH wrapper that satisfies the Shell protocol."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 2222,
        user: str = "root",
        key_path: str | None = None,
        password: str | None = None,
        ssh_binary: str = "ssh",
        scp_binary: str = "scp",
    ):
        self.host = host
        self.port = int(port)
        self.user = user
        self.key_path = key_path
        self.password = password
        self.ssh_binary = ssh_binary
        self.scp_binary = scp_binary

    def _base_opts(self) -> list[str]:
        opts = [
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR",
            "-o", "ConnectTimeout=10",
        ]
        if self.key_path:
            opts += ["-i", self.key_path, "-o", "IdentitiesOnly=yes"]
        return opts

    def _ssh_cmd(self, remote_cmd: str) -> list[str]:
        cmd: list[str] = []
        if self.password and not self.key_path:
            cmd += ["sshpass", "-p", self.password]
        cmd += [self.ssh_binary, "-p", str(self.port)] + self._base_opts()
        cmd += [f"{self.user}@{self.host}", remote_cmd]
        return cmd

    def shell(
        self,
        cmd: str,
        *,
        timeout: float | None = 60,
        check: bool = True,
        as_root: bool = False,
    ) -> ShellResult:
        # `as_root` is a no-op when self.user == 'root', which is the norm for
        # jailbroken iOS. Kept for Shell-protocol compatibility.
        full = self._ssh_cmd(cmd)
        log.debug("ssh cmd: %s", " ".join(shlex.quote(c) for c in full))
        proc = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
        result = ShellResult(proc.returncode, proc.stdout, proc.stderr)
        if check and not result.ok:
            raise SshError(full, result.returncode, result.stdout, result.stderr)
        return result

    def push(self, local: str, remote: str) -> None:
        cmd: list[str] = []
        if self.password and not self.key_path:
            cmd += ["sshpass", "-p", self.password]
        cmd += [self.scp_binary, "-P", str(self.port)] + self._base_opts()
        cmd += [local, f"{self.user}@{self.host}:{remote}"]
        subprocess.run(cmd, check=True, capture_output=True, text=True)

    def pull(self, remote: str, local: str) -> None:
        cmd: list[str] = []
        if self.password and not self.key_path:
            cmd += ["sshpass", "-p", self.password]
        cmd += [self.scp_binary, "-P", str(self.port)] + self._base_opts()
        cmd += [f"{self.user}@{self.host}:{remote}", local]
        subprocess.run(cmd, check=True, capture_output=True, text=True)

    def reachable(self) -> bool:
        try:
            return self.shell("echo OK", timeout=10, check=False).stdout.strip() == "OK"
        except Exception:
            return False
