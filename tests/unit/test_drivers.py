import subprocess

import pytest

from dot11test.android.adb import Adb, AdbError
from dot11test.ios.ssh import Ssh
from dot11test.shell import Shell

pytestmark = pytest.mark.unit


class FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


@pytest.fixture
def capture_run(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return FakeProc(0, "OK\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def test_both_drivers_satisfy_shell_protocol():
    assert isinstance(Adb(), Shell)
    assert isinstance(Ssh(), Shell)


def test_adb_shell_with_serial(capture_run):
    Adb(serial="ABC123").shell("echo hi")
    assert capture_run[0] == ["adb", "-s", "ABC123", "shell", "echo hi"]


def test_adb_shell_as_root_wraps_su(capture_run):
    Adb().shell("svc wifi enable", as_root=True)
    assert capture_run[0] == ["adb", "shell", "su -c 'svc wifi enable'"]


def test_adb_raises_on_failure(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: FakeProc(1, "", "boom"))
    with pytest.raises(AdbError, match="boom"):
        Adb().shell("false")
    assert Adb().shell("false", check=False).returncode == 1


def test_adb_devices_parsing(monkeypatch):
    out = "List of devices attached\nABC123\tdevice\nDEF456\tunauthorized\nGHI789\tdevice\n\n"
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: FakeProc(0, out))
    assert Adb().devices() == ["ABC123", "GHI789"]


def test_ssh_command_with_key(capture_run):
    Ssh(port=2222, key_path="/k/id").shell("uname -a")
    cmd = capture_run[0]
    assert cmd[0] == "ssh"
    assert cmd[cmd.index("-p") + 1] == "2222"
    assert cmd[cmd.index("-i") + 1] == "/k/id"
    assert cmd[-2:] == ["root@127.0.0.1", "uname -a"]
    assert "sshpass" not in cmd


def test_ssh_password_uses_sshpass(capture_run):
    Ssh(password="alpine").shell("id")
    assert capture_run[0][:3] == ["sshpass", "-p", "alpine"]


def test_scp_push_uses_capital_p(capture_run):
    Ssh(port=2222).push("local.bin", "/tmp/x")
    cmd = capture_run[0]
    assert cmd[0] == "scp" and cmd[cmd.index("-P") + 1] == "2222"
    assert cmd[-2:] == ["local.bin", "root@127.0.0.1:/tmp/x"]


def test_ssh_reachable(capture_run):
    assert Ssh().reachable() is True
