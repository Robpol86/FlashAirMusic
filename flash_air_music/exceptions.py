"""All custom exceptions raised by the program."""


class BaseError(Exception):
    """Base class for other narrow-scoped exceptions."""

    pass


class ConfigError(BaseError):
    """Error while reading configuration data."""

    pass
