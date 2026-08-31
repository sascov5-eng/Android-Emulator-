from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from app.stream.process import FFmpegScreenrecordAdapter


@dataclass
class FakeProc:
    args: list[str]
    stdout: object | None = None
    stderr: object | None = None
    returncode: int | None = None
    terminated: bool = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode or 0

    def kill(self):
        self.returncode = -9


class FakePopen:
    def __init__(self):
        self.calls: list[tuple[list[str], dict]] = []
        self.procs: list[FakeProc] = []

    def __call__(self, args, **kwargs):
        proc = FakeProc(list(args))
        if len(self.procs) == 0:
            proc.stdout = BytesIO()
            proc.stderr = BytesIO()
        else:
            proc.stderr = BytesIO()
        self.calls.append((list(args), kwargs))
        self.procs.append(proc)
        return proc


def make_adapter(popen: FakePopen) -> FFmpegScreenrecordAdapter:
    return FFmpegScreenrecordAdapter(
        adb_bin="adb",
        adb_target="127.0.0.1:5555",
        ffmpeg_bin="ffmpeg",
        rtsp_url="rtsp://127.0.0.1:8554/android/session",
        width=720,
        height=1280,
        fps=30,
        bitrate=4_000_000,
        capture_seconds=175,
        popen=popen,
        sleep=lambda _: None,
    )


def test_start_capture_uses_argument_arrays_and_private_rtsp() -> None:
    popen = FakePopen()
    adapter = make_adapter(popen)

    adapter.start_capture()

    adb_args, adb_kwargs = popen.calls[0]
    ffmpeg_args, ffmpeg_kwargs = popen.calls[1]

    assert adb_args == [
        "adb", "-s", "127.0.0.1:5555", "exec-out", "screenrecord",
        "--output-format=h264", "--bit-rate", "4000000",
        "--size", "720x1280", "--time-limit", "175", "-",
    ]
    assert ffmpeg_args == [
        "ffmpeg", "-hide_banner", "-loglevel", "warning",
        "-fflags", "nobuffer", "-flags", "low_delay",
        "-f", "h264", "-i", "pipe:0",
        "-an", "-c:v", "copy", "-f", "rtsp", "-rtsp_transport", "tcp",
        "rtsp://127.0.0.1:8554/android/session",
    ]
    assert adb_kwargs.get("shell") is False
    assert ffmpeg_kwargs.get("shell") is False
    assert ffmpeg_kwargs["stdin"] is popen.procs[0].stdout


def test_adapter_reports_alive_only_when_both_processes_are_alive() -> None:
    popen = FakePopen()
    adapter = make_adapter(popen)
    adapter.start_capture()

    assert adapter.is_alive() is True

    popen.procs[1].returncode = 1
    assert adapter.is_alive() is False


def test_stop_capture_terminates_both_processes() -> None:
    popen = FakePopen()
    adapter = make_adapter(popen)
    adapter.start_capture()

    adapter.stop_capture()

    assert all(proc.terminated for proc in popen.procs)


def test_wait_until_live_requires_processes_to_stay_alive() -> None:
    popen = FakePopen()
    adapter = make_adapter(popen)
    adapter.start_capture()

    assert adapter.wait_until_live(0.1) is True

    popen.procs[0].returncode = 1
    assert adapter.wait_until_live(0.1) is False
