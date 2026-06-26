from inspect import signature
from urllib.parse import urlencode  # noqa: F401

from aiohttp import StreamReader
from aiohttp.client_proto import ResponseHandler
from multidict import MultiDict
from yarl import URL


class _MockResponseHandler(ResponseHandler):
    """ResponseHandler that no-ops pause_reading for mock contexts."""

    def pause_reading(self) -> None:
        pass


def stream_reader_factory(loop=None) -> StreamReader:
    rh_params = signature(ResponseHandler.__init__).parameters
    protocol = _MockResponseHandler(loop=loop) if "loop" in rh_params else _MockResponseHandler()

    sr_params = signature(StreamReader.__init__).parameters
    if "loop" in sr_params:
        return StreamReader(protocol, limit=2**16, loop=loop)
    return StreamReader(protocol, limit=2**16)


def merge_params(url: URL | str, params: dict | None = None) -> URL:
    url = URL(url)
    if params:
        query_params = MultiDict(url.query)
        query_params.extend(url.with_query(params).query)
        return url.with_query(query_params)
    return url


def normalize_url(url: URL | str) -> URL:
    """Normalize url to make comparisons."""
    url = URL(url)
    return url.with_query(sorted(url.query.items()))


__all__ = [
    "merge_params",
    "normalize_url",
    "stream_reader_factory",
]
