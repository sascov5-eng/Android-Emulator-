from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Callable, Protocol

from .errors import ADBCommandError, AppResolutionError, RuntimeBootTimeout
from .models import AndroidApp


class _ProcessResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[..., _ProcessResult]


class SubprocessADBClient:
    def __init__(
        self,
        *,
        adb_bin: str = "adb",
        aapt_bin: str | None = "aapt",
        runner: Runner = subprocess.run,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        poll_interval_seconds: float = 0.5,
    ) -> None:
        if not adb_bin.strip():
            raise ValueError("adb_bin must not be empty")
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        self._adb_bin = adb_bin
        self._aapt_bin = aapt_bin
        self._runner = runner
        self._clock = clock
        self._sleeper = sleeper
        self._poll_interval_seconds = poll_interval_seconds

    def _run(self, args: list[str], timeout: float | None = None) -> _ProcessResult:
        try:
            result = self._runner(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            raise ADBCommandError("Android device command failed") from exc

        if result.returncode != 0:
            raise ADBCommandError("Android device command failed")
        return result

    def _adb(self, target: str, *args: str, timeout: float | None = None) -> _ProcessResult:
        return self._run(
            [self._adb_bin, "-s", target, *args],
            timeout=timeout,
        )

    def wait_for_device(self, target: str, timeout_seconds: float) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        connect = self._run(
            [self._adb_bin, "connect", target],
            timeout=timeout_seconds,
        )
        if "failed" in connect.stdout.lower() or "unable" in connect.stdout.lower():
            raise ADBCommandError("Android device connection failed")
        self._adb(target, "wait-for-device", timeout=timeout_seconds)

    def wait_for_boot(self, target: str, timeout_seconds: float) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        deadline = self._clock() + timeout_seconds
        while True:
            try:
                result = self._adb(
                    target,
                    "shell",
                    "getprop",
                    "sys.boot_completed",
                    timeout=min(timeout_seconds, 10.0),
                )
                if result.stdout.strip() == "1":
                    return
            except ADBCommandError:
                # During Android boot ADB may transiently disconnect. Keep polling
                # until the lifecycle timeout expires.
                pass

            if self._clock() >= deadline:
                raise RuntimeBootTimeout("Android boot timed out")
            self._sleeper(self._poll_interval_seconds)

    def install(self, target: str, apk_path: Path) -> None:
        self._adb(target, "install", "-r", str(apk_path))

    @staticmethod
    def _quoted_value(text: str, key: str) -> str | None:
        match = re.search(rf"\b{re.escape(key)}='([^']*)'", text)
        return match.group(1) if match else None

    def resolve_launchable(self, target: str, apk_path: Path) -> AndroidApp:
        del target  # metadata is resolved locally from the canonical APK file
        if self._aapt_bin is None:
            raise AppResolutionError("Android application metadata could not be resolved")

        try:
            result = self._run([self._aapt_bin, "dump", "badging", str(apk_path)])
        except ADBCommandError as exc:
            raise AppResolutionError(
                "Android application metadata could not be resolved"
            ) from exc

        package_name: str | None = None
        activity_name: str | None = None
        label: str | None = None

        for line in result.stdout.splitlines():
            if line.startswith("package:"):
                package_name = self._quoted_value(line, "name")
            elif line.startswith("launchable-activity:"):
                activity_name = self._quoted_value(line, "name")
                label = self._quoted_value(line, "label") or label
            elif line.startswith("application-label:") and label is None:
                label_match = re.match(r"application-label:'([^']*)'", line)
                if label_match:
                    label = label_match.group(1)

        if not package_name:
            raise AppResolutionError("Android application metadata could not be resolved")

        return AndroidApp(
            package_name=package_name,
            activity_name=activity_name,
            label=label,
        )

    def launch(
        self,
        target: str,
        package_name: str,
        activity_name: str | None,
    ) -> None:
        if activity_name:
            self._adb(
                target,
                "shell",
                "am",
                "start",
                "-n",
                f"{package_name}/{activity_name}",
            )
            return

        self._adb(
            target,
            "shell",
            "monkey",
            "-p",
            package_name,
            "1",
        )

    def list_apps(self, target: str) -> list[AndroidApp]:
        result = self._adb(target, "shell", "pm", "list", "packages", "-3")
        apps: list[AndroidApp] = []
        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()
            if not line.startswith("package:"):
                continue
            package_name = line.removeprefix("package:").strip()
            if package_name:
                apps.append(AndroidApp(package_name=package_name))
        return apps
