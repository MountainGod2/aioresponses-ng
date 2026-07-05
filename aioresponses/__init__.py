from importlib.metadata import PackageNotFoundError, version

from .core import CallbackResult, aioresponses

try:
    __version__: str = version("aioresponses-ng")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

__all__ = [
    "CallbackResult",
    "aioresponses",
]
