from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.runtime.adb import SubprocessADBClient
from app.runtime.errors import ADBCommandError, AppResolutionError, RuntimeBootTimeout


class RecordingRunner:
    def __init__(self, outputs: list[tuple[int, str, str]] | None = None) -> None:
        self.calls: list[tuple[list[str], float | None]] = []
        self.outputs = list(outputs or [])

    def __call__(
        self,
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float | None = None,
        check: bool = False,
    ) -> SimpleNamespace:
        assert capture_output is True
        assert text is True
        assert check is False
        self.calls.append((list(args), timeout))
        if self.outputs:
            returncode, stdout, stderr = self.outputs.pop(0)
        else:
            returncode, stdout, stderr = 0, "", ""
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_wait_for_device_connects_and_waits() -> None:
    runner = RecordingRunner()
    client = SubprocessADBClient(adb_bin="adb", runner=runner)

    client.wait_for_device("127.0.0.1:5555", 9.0)

    assert runner.calls == [
        (["adb", "connect", "127.0.0.1:5555"], 9.0),
        (["adb", "-s", "127.0.0.1:5555", "wait-for-device"], 9.0),
    ]


def test_wait_for_boot_polls_getprop_until_one() -> None:
    runner = RecordingRunner(
        [
            (0, "0\n", ""),
            (0, "1\n", ""),
        ]
    )
    times = iter([0.0, 0.0, 0.1, 0.2])
    client = SubprocessADBClient(
        adb_bin="adb",
        runner=runner,
        clock=lambda: next(times),
        sleeper=lambda _: None,
        poll_interval_seconds=0.01,
    )

    client.wait_for_boot("127.0.0.1:5555", 5.0)

    assert [call[0] for call in runner.calls] == [
        ["adb", "-s", "127.0.0.1:5555", "shell", "getprop", "sys.boot_completed"],
        ["adb", "-s", "127.0.0.1:5555", "shell", "getprop", "sys.boot_completed"],
    ]


def test_wait_for_boot_raises_sanitized_timeout() -> None:
    runner = RecordingRunner([(0, "0\n", "")])
    times = iter([0.0, 0.0, 2.0])
    client = SubprocessADBClient(
        runner=runner,
        clock=lambda: next(times),
        sleeper=lambda _: None,
    )

    with pytest.raises(RuntimeBootTimeout, match="timed out"):
        client.wait_for_boot("127.0.0.1:5555", 1.0)


def test_install_uses_replace_flag_and_canonical_path(tmp_path: Path) -> None:
    apk = tmp_path / "game.apk"
    apk.write_bytes(b"apk")
    runner = RecordingRunner()
    client = SubprocessADBClient(adb_bin="custom-adb", runner=runner)

    client.install("127.0.0.1:5555", apk)

    assert runner.calls[0][0] == [
        "custom-adb",
        "-s",
        "127.0.0.1:5555",
        "install",
        "-r",
        str(apk),
    ]


def test_resolve_launchable_parses_aapt_badging(tmp_path: Path) -> None:
    apk = tmp_path / "game.apk"
    apk.write_bytes(b"apk")
    runner = RecordingRunner(
        [
            (
                0,
                "package: name='com.example.game' versionCode='1'\n"
                "application-label:'Example Game'\n"
                "launchable-activity: name='com.example.game.MainActivity' label='Example Game' icon=''\n",
                "",
            )
        ]
    )
    client = SubprocessADBClient(aapt_bin="aapt", runner=runner)

    app = client.resolve_launchable("127.0.0.1:5555", apk)

    assert runner.calls[0][0] == ["aapt", "dump", "badging", str(apk)]
    assert app.package_name == "com.example.game"
    assert app.activity_name == "com.example.game.MainActivity"
    assert app.label == "Example Game"


def test_resolve_launchable_requires_package_metadata(tmp_path: Path) -> None:
    apk = tmp_path / "bad.apk"
    apk.write_bytes(b"apk")
    runner = RecordingRunner([(0, "application-label:'Unknown'\n", "")])
    client = SubprocessADBClient(aapt_bin="aapt", runner=runner)

    with pytest.raises(AppResolutionError):
        client.resolve_launchable("127.0.0.1:5555", apk)


def test_launch_uses_activity_when_available() -> None:
    runner = RecordingRunner()
    client = SubprocessADBClient(runner=runner)

    client.launch("127.0.0.1:5555", "com.example.game", ".MainActivity")

    assert runner.calls[0][0] == [
        "adb",
        "-s",
        "127.0.0.1:5555",
        "shell",
        "am",
        "start",
        "-n",
        "com.example.game/.MainActivity",
    ]


def test_launch_falls_back_to_monkey_without_activity() -> None:
    runner = RecordingRunner()
    client = SubprocessADBClient(runner=runner)

    client.launch("127.0.0.1:5555", "com.example.game", None)

    assert runner.calls[0][0] == [
        "adb",
        "-s",
        "127.0.0.1:5555",
        "shell",
        "monkey",
        "-p",
        "com.example.game",
        "1",
    ]


def test_list_apps_parses_third_party_packages() -> None:
    runner = RecordingRunner(
        [(0, "package:com.alpha\npackage:com.beta\nnoise\n", "")]
    )
    client = SubprocessADBClient(runner=runner)

    apps = client.list_apps("127.0.0.1:5555")

    assert runner.calls[0][0] == [
        "adb",
        "-s",
        "127.0.0.1:5555",
        "shell",
        "pm",
        "list",
        "packages",
        "-3",
    ]
    assert [app.package_name for app in apps] == ["com.alpha", "com.beta"]


def test_nonzero_adb_exit_does_not_leak_stderr() -> None:
    runner = RecordingRunner([(1, "", "super secret adb stderr")])
    client = SubprocessADBClient(runner=runner)

    with pytest.raises(ADBCommandError) as caught:
        client.list_apps("127.0.0.1:5555")

    assert "secret" not in str(caught.value).lower()
