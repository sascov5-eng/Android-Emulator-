from __future__ import annotations


class StreamErrorBase(Exception):
    """Base class for stream-domain failures."""


class StreamStartError(StreamErrorBase):
    pass


class StreamUnavailable(StreamErrorBase):
    pass


class StreamStopError(StreamErrorBase):
    pass


class InputValidationError(StreamErrorBase):
    pass


class InputCommandError(StreamErrorBase):
    pass
