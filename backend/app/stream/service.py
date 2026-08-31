from __future__ import annotations

from typing import Any

from app.runtime.errors import RuntimeNotReady
from app.runtime.models import RuntimeState

from .errors import StreamErrorBase, StreamStartError, StreamStopError, StreamUnavailable
from .interfaces import StreamProcessAdapter
from .models import StreamState, StreamStatus


class StreamManager:
    def __init__(
        self,
        *,
        runtime: Any,
        process_adapter: StreamProcessAdapter,
        whep_url: str,
        width: int,
        height: int,
        fps: int,
        start_timeout_seconds: float,
        session_id: str = "default",
    ) -> None:
        self._runtime = runtime
        self._process = process_adapter
        self._whep_url = whep_url
        self._width = width
        self._height = height
        self._fps = fps
        self._start_timeout_seconds = start_timeout_seconds
        self._session_id = session_id
        self._state = StreamState.STOPPED
        self._error: str | None = None

    def _status(self) -> StreamStatus:
        return StreamStatus(
            state=self._state,
            session_id=self._session_id,
            whep_url=self._whep_url if self._state is StreamState.LIVE else None,
            width=self._width,
            height=self._height,
            fps=self._fps,
            error=self._error,
        )

    def _restart_expired_segment(self) -> None:
        try:
            self._process.start_capture()
            if not self._process.wait_until_live(self._start_timeout_seconds):
                try:
                    self._process.stop_capture()
                except Exception:
                    pass
                raise StreamUnavailable("stream segment did not become live")
        except Exception:
            self._state = StreamState.ERROR
            self._error = "Android stream is not available"
            return

        self._state = StreamState.LIVE
        self._error = None

    def status(self) -> StreamStatus:
        if self._state is StreamState.LIVE and not self._process.is_alive():
            # Android's screenrecord is intentionally capped below its hard
            # 180-second limit. Treat a cleanly ended capture as a segment
            # boundary and rebuild the capture/publish pipe on the next
            # status check rather than failing the user session immediately.
            self._restart_expired_segment()
        return self._status()

    def start(self) -> StreamStatus:
        runtime_status = self._runtime.status()
        if runtime_status.state is not RuntimeState.READY:
            raise RuntimeNotReady("runtime must be ready before starting stream")

        if self._state is StreamState.LIVE and self._process.is_alive():
            return self._status()

        self._state = StreamState.STARTING
        self._error = None
        try:
            self._process.start_capture()
            if not self._process.wait_until_live(self._start_timeout_seconds):
                self._process.stop_capture()
                self._state = StreamState.ERROR
                self._error = "Android stream is not available"
                raise StreamUnavailable("stream did not become live")
        except StreamErrorBase:
            self._state = StreamState.ERROR
            self._error = "Android stream failed to start"
            raise
        except Exception as exc:
            self._state = StreamState.ERROR
            self._error = "Android stream failed to start"
            raise StreamStartError("stream process failed") from exc

        self._state = StreamState.LIVE
        return self._status()

    def stop(self) -> StreamStatus:
        if self._state is StreamState.STOPPED:
            return self._status()

        try:
            if self._process.is_alive():
                self._process.stop_capture()
        except Exception as exc:
            self._state = StreamState.ERROR
            self._error = "Android stream failed to stop"
            raise StreamStopError("stream stop failed") from exc

        self._state = StreamState.STOPPED
        self._error = None
        return self._status()
