from __future__ import annotations

import subprocess
from typing import Callable, Protocol

from .errors import RuntimeDriverError
from .models import RuntimeEndpoint


class _ProcessResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[..., _ProcessResult]


class DockerRuntimeDriver:
    def __init__(
        self,
        *,
        docker_bin: str = "docker",
        image: str,
        runtime_name: str,
        volume_name: str,
        adb_host: str,
        adb_port: int,
        runner: Runner = subprocess.run,
        command_timeout_seconds: float = 30.0,
    ) -> None:
        if adb_host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("adb_host must be a loopback address")
        if not 1 <= adb_port <= 65535:
            raise ValueError("adb_port must be between 1 and 65535")
        if not docker_bin.strip() or not image.strip() or not runtime_name.strip():
            raise ValueError("docker runtime configuration must not be empty")
        if not volume_name.strip():
            raise ValueError("volume_name must not be empty")
        if command_timeout_seconds <= 0:
            raise ValueError("command_timeout_seconds must be positive")
        self._docker_bin = docker_bin
        self._image = image
        self._runtime_name = runtime_name
        self._volume_name = volume_name
        self._adb_host = adb_host
        self._adb_port = adb_port
        self._runner = runner
        self._command_timeout_seconds = command_timeout_seconds

    @property
    def endpoint(self) -> RuntimeEndpoint:
        return RuntimeEndpoint(adb_host=self._adb_host, adb_port=self._adb_port)

    def _run(
        self,
        args: list[str],
        *,
        allow_failure: bool = False,
    ) -> _ProcessResult:
        try:
            result = self._runner(
                args,
                capture_output=True,
                text=True,
                timeout=self._command_timeout_seconds,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            raise RuntimeDriverError("Docker runtime command failed") from exc

        if result.returncode != 0 and not allow_failure:
            raise RuntimeDriverError("Docker runtime command failed")
        return result

    def exists(self) -> bool:
        result = self._run(
            [
                self._docker_bin,
                "inspect",
                "-f",
                "{{.State.Running}}",
                self._runtime_name,
            ],
            allow_failure=True,
        )
        return result.returncode == 0 and result.stdout.strip().lower() == "true"

    def _start_new(self) -> RuntimeEndpoint:
        self._run(
            [
                self._docker_bin,
                "run",
                "-d",
                "--rm",
                "--privileged",
                "--name",
                self._runtime_name,
                "-p",
                f"{self._adb_host}:{self._adb_port}:5555",
                "-v",
                f"{self._volume_name}:/data",
                self._image,
            ]
        )
        return self.endpoint

    def start(self) -> RuntimeEndpoint:
        if self.exists():
            return self.endpoint
        return self._start_new()

    def stop(self) -> None:
        if not self.exists():
            return
        self._run([self._docker_bin, "rm", "-f", self._runtime_name])

    def reset(self) -> RuntimeEndpoint:
        if self.exists():
            self._run([self._docker_bin, "rm", "-f", self._runtime_name])
        self._run(
            [
                self._docker_bin,
                "volume",
                "rm",
                "-f",
                self._volume_name,
            ],
            allow_failure=True,
        )
        return self._start_new()
