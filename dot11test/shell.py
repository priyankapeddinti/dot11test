"""Shell protocol satisfied by every platform driver.

Anything that can `shell(cmd) -> ShellResult` and `push(local, remote)` can
drive iperf, ping, and other tools that just need to execute commands on the
device under test.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from .types import ShellResult


@runtime_checkable
class Shell(Protocol):
    def shell(
        self,
        cmd: str,
        *,
        timeout: float | None = 60,
        check: bool = True,
        as_root: bool = False,
    ) -> ShellResult: ...

    def push(self, local: str, remote: str) -> None: ...

    def pull(self, remote: str, local: str) -> None: ...
