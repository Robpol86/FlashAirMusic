"""All custom exceptions raised by the program."""


class BaseError(Exception):
    """Base class for other narrow-scoped exceptions."""

    pass


class ConfigError(BaseError):
    """Error while reading configuration data."""

    pass


class CorruptedTargetFile(BaseError):
    """Error while operating on convered target file."""

    pass


class ShuttingDown(BaseError):
    """Raised when shutdown_future is set."""

    pass
