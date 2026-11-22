from __future__ import annotations

import re

import pytest

from dot11test.types import ShellResult


class FakeShell:
    """Shell double: maps regex patterns to canned responses and records calls."""

    def __init__(self, responses: dict[str, str | ShellResult] | None = None):
        self.responses = dict(responses or {})
        self.calls: list[str] = []

    def shell(self, cmd, *, timeout=60, check=True, as_root=False) -> ShellResult:
        self.calls.append(cmd)
        for pattern, resp in self.responses.items():
            if re.search(pattern, cmd):
                if isinstance(resp, ShellResult):
                    return resp
                return ShellResult(0, resp, "")
        return ShellResult(0, "", "")

    def push(self, local, remote):
        self.calls.append(f"push {local} {remote}")

    def pull(self, remote, local):
        self.calls.append(f"pull {remote} {local}")


@pytest.fixture
def fake_shell():
    return FakeShell
