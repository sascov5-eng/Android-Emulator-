from __future__ import annotations


class RuntimeErrorBase(Exception):
    """Base class for client-safe runtime errors."""


class RuntimeDriverError(RuntimeErrorBase):
    pass


class RuntimeBootTimeout(RuntimeErrorBase):
    pass


class RuntimeNotReady(RuntimeErrorBase):
    pass


class ADBCommandError(RuntimeErrorBase):
    pass


class APKNotFound(RuntimeErrorBase):
    pass


class APKFileMissing(RuntimeErrorBase):
    pass


class AppResolutionError(RuntimeErrorBase):
    pass


class AppLaunchError(RuntimeErrorBase):
    pass
