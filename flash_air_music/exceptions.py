"""All custom exceptions raised by the program."""


class BaseError(Exception):
    """Base class for other narrow-scoped exceptions."""


class ConfigError(BaseError):
    """Error while reading configuration data."""


class CorruptedTargetFile(BaseError):
    """Error while operating on converted target file."""


class FlashAirError(BaseError):
    """Error while accessing the FlashAir card's API."""


class FlashAirDirNotFoundError(FlashAirError):
    """Directory not found on card."""


class FlashAirHTTPError(FlashAirError):
    """API returned non-200 status code."""


class FlashAirBadResponse(FlashAirError):
    """Unexpected data returned by API."""


class ShuttingDown(BaseError):
    """Raised when shutdown_future is set."""
