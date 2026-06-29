import asyncio
import re
from asyncio import CancelledError, TimeoutError
from random import uniform
from unittest.mock import patch

import pytest
from aiohttp import hdrs, http, web
from aiohttp.client import ClientSession
from aiohttp.client_exceptions import ClientConnectionError, ClientResponseError
from aiohttp.client_reqrep import ClientResponse
from aiohttp.http_exceptions import HttpProcessingError
from aiohttp.test_utils import TestServer
from multidict import CIMultiDict
from packaging.version import Version
from yarl import URL

from aioresponses import CallbackResult, aioresponses
from aioresponses.core import AIOHTTP_VERSION


class TestAIOResponses:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.url = "http://example.com/api?foo=bar#fragment"
        self.session = ClientSession()
        yield
        await self.session.close()

    async def request(self, url: str) -> ClientResponse:
        return await self.session.get(url)

    @pytest.mark.parametrize(
        "http_method",
        [
            hdrs.METH_HEAD,
            hdrs.METH_GET,
            hdrs.METH_POST,
            hdrs.METH_PUT,
            hdrs.METH_PATCH,
            hdrs.METH_DELETE,
            hdrs.METH_OPTIONS,
        ],
    )
    async def test_shortcut_method(self, http_method: str) -> None:
        with patch("aioresponses.aioresponses.add") as mocked, aioresponses() as m:
            getattr(m, http_method.lower())(self.url)
            mocked.assert_called_once_with(self.url, method=http_method)

    async def test_returned_instance(self) -> None:
        with aioresponses() as m:
            m.get(self.url)
            response = await self.session.get(self.url)
        assert isinstance(response, ClientResponse)

    async def test_returned_instance_and_status_code(self) -> None:
        with aioresponses() as m:
            m.get(self.url, status=204)
            response = await self.session.get(self.url)
        assert isinstance(response, ClientResponse)
        assert response.status == 204

    @pytest.mark.parametrize(
        "base_url,relative_url",
        [
            ("http://example.com", "/api?foo=bar#fragment"),
            ("http://example.com/", "/api?foo=bar#fragment"),
        ],
    )
    @pytest.mark.skipif(Version("3.9.0") > AIOHTTP_VERSION, reason="aiohttp must be >= 3.9.0")
    async def test_base_url(self, base_url: str, relative_url: str) -> None:
        with aioresponses() as m:
            m.get(self.url, status=200)
            async with ClientSession(base_url=base_url) as session:
                response = await session.get(relative_url)
        assert response.status == 200

    @pytest.mark.skipif(Version("3.9.0") > AIOHTTP_VERSION, reason="aiohttp must be >= 3.9.0")
    async def test_session_headers(self) -> None:
        with aioresponses() as m:
            m.get(self.url)
            async with ClientSession(headers={"Authorization": "Bearer foobar"}) as session:
                response = await session.get(self.url)

        assert response.status == 200
        request = m.requests[("GET", URL(self.url))][0]
        assert request.kwargs["headers"]["Authorization"] == "Bearer foobar"

    async def test_returned_response_headers(self) -> None:
        with aioresponses() as m:
            m.get(self.url, content_type="text/html", headers={"Connection": "keep-alive"})
            response = await self.session.get(self.url)

        assert response.headers["Connection"] == "keep-alive"
        assert response.headers[hdrs.CONTENT_TYPE] == "text/html"

    async def test_returned_response_multidict_headers(self) -> None:
        header_name = "x-custom-header"
        header_values = ["foo", "bar"]
        with aioresponses() as m:
            m.get(
                self.url,
                content_type="text/html",
                headers=CIMultiDict([(header_name, v) for v in header_values]),
            )
            response = await self.session.get(self.url)

        assert response.headers.getall(header_name) == header_values

    async def test_returned_response_cookies(self) -> None:
        with aioresponses() as m:
            m.get(self.url, headers={"Set-Cookie": "cookie=value"})
            response = await self.session.get(self.url)

        assert response.cookies["cookie"].value == "value"

    async def test_returned_response_raw_headers(self) -> None:
        with aioresponses() as m:
            m.get(self.url, content_type="text/html", headers={"Connection": "keep-alive"})
            response = await self.session.get(self.url)

        expected = (
            (hdrs.CONTENT_TYPE.encode(), b"text/html"),
            (b"Connection", b"keep-alive"),
        )
        assert response.raw_headers == expected

    async def test_raise_for_status(self) -> None:
        with aioresponses() as m:
            m.get(self.url, status=400)
            with pytest.raises(ClientResponseError) as exc_info:
                response = await self.session.get(self.url)
                response.raise_for_status()
        assert exc_info.value.message == http.RESPONSES[400][0]

    async def test_request_raise_for_status(self) -> None:
        with aioresponses() as m:
            m.get(self.url, status=400)
            with pytest.raises(ClientResponseError) as exc_info:
                await self.session.get(self.url, raise_for_status=True)
        assert exc_info.value.message == http.RESPONSES[400][0]

    async def test_returned_instance_and_params_handling(self) -> None:
        with aioresponses() as m:
            m.get("http://example.com/api?foo=bar&x=42#fragment")
            response = await self.session.get(self.url, params={"x": 42})
            assert isinstance(response, ClientResponse)
            assert response.status == 200

            m.get("http://example.com/api?x=42#fragment")
            response = await self.session.get("http://example.com/api#fragment", params={"x": 42})
            assert isinstance(response, ClientResponse)
            assert response.status == 200
            assert len(m.requests) == 2

            with pytest.raises(AssertionError):
                m.assert_called_once()

    async def test_method_dont_match(self) -> None:
        with aioresponses() as m:
            m.get(self.url)
            with pytest.raises(ClientConnectionError):
                await self.session.post(self.url)

    async def test_post_with_data(self) -> None:
        body = b"New body"
        with aioresponses() as m:
            m.post(self.url, body=body)
            response = await self.session.post(self.url)
            data = await response.read()
        assert data == body

    async def test_binary_body(self) -> None:
        body = b"\x00\x01\x02\x80\x81\x82\x83\x84\x85"
        with aioresponses() as m:
            m.get(self.url, body=body)
            resp = await self.session.get(self.url)
            content = await resp.read()
        assert content == body

    async def test_binary_body_via_callback(self) -> None:
        body = b"\x00\x01\x02\x80\x81\x82\x83\x84\x85"

        def callback(url, **kwargs):
            return CallbackResult(body=body)

        with aioresponses() as m:
            m.get(self.url, callback=callback)
            resp = await self.session.get(self.url)
            content = await resp.read()
        assert content == body

    async def test_mocking_as_context_manager(self) -> None:
        with aioresponses() as aiomock:
            aiomock.add(self.url, payload={"foo": "bar"})
            resp = await self.session.get(self.url)
            assert resp.status == 200
            payload = await resp.json()
        assert payload == {"foo": "bar"}

    async def test_mocking_as_async_context_manager(self) -> None:
        async with aioresponses() as aiomock:
            aiomock.add(self.url, payload={"foo": "bar"})
            resp = await self.session.get(self.url)
            assert resp.status == 200
            payload = await resp.json()
        assert payload == {"foo": "bar"}

    async def test_mocking_as_decorator(self) -> None:
        url = self.url

        @aioresponses()
        async def foo(m: aioresponses) -> None:
            m.add(url, payload={"foo": "bar"})
            async with ClientSession() as session:
                resp = await session.get(url)
                assert resp.status == 200
                payload = await resp.json()
            assert payload == {"foo": "bar"}

        await foo()

    async def test_passing_argument(self) -> None:
        @aioresponses(param="mocked")
        async def foo(mocked: aioresponses) -> None:
            mocked.add(self.url, payload={"foo": "bar"})
            resp = await self.session.get(self.url)
            assert resp.status == 200

        await foo()

    async def test_mocking_as_decorator_wrong_mocked_arg_name(self) -> None:
        @aioresponses(param="foo")
        def foo(bar):
            pass

        with pytest.raises(TypeError, match="got an unexpected keyword argument 'foo'"):
            foo()

    async def test_unknown_request(self) -> None:
        with aioresponses() as aiomock:
            aiomock.add(self.url, payload={"foo": "bar"})
            with pytest.raises(ClientConnectionError):
                await self.session.get("http://example.com/foo")

    async def test_raising_exception(self) -> None:
        with aioresponses() as aiomock:
            for url, exc in [
                ("http://example.com/Exception", Exception),
                ("http://example.com/Exception_object", Exception()),
                ("http://example.com/BaseException", BaseException),
                ("http://example.com/BaseException_object", BaseException()),
                ("http://example.com/CancelError", CancelledError),
                ("http://example.com/TimeoutError", TimeoutError),
            ]:
                aiomock.get(url, exception=exc)
                with pytest.raises(BaseException):  # noqa: B017
                    await self.session.get(url)

            url = "http://example.com/HttpProcessingError"
            aiomock.get(url, exception=HttpProcessingError(message="foo"))
            with pytest.raises(HttpProcessingError):
                await self.session.get(url)

            callback_called = asyncio.Event()
            aiomock.get(
                url,
                exception=HttpProcessingError(message="foo"),
                callback=lambda *_, **__: callback_called.set(),
            )
            with pytest.raises(HttpProcessingError):
                await self.session.get(url)
            await callback_called.wait()

    async def test_exceptions_in_the_middle_of_responses(self) -> None:
        with aioresponses() as mocked:
            mocked.get(self.url, payload={}, status=204)
            mocked.get(self.url, exception=ValueError("oops"))
            mocked.get(self.url, payload={}, status=204)
            mocked.get(self.url, exception=ValueError("oops"))
            mocked.get(self.url, payload={}, status=200)

            assert (await self.session.get(self.url)).status == 204
            with pytest.raises(ValueError):
                await self.session.get(self.url)
            assert (await self.session.get(self.url)).status == 204
            with pytest.raises(ValueError):
                await self.session.get(self.url)
            assert (await self.session.get(self.url)).status == 200

    async def test_multiple_requests(self) -> None:
        with aioresponses() as m:
            m.get(self.url, status=200)
            m.get(self.url, status=201)
            m.get(self.url, status=202)
            json_ref = [1]
            resp = await self.session.get(self.url, json=json_ref)
            assert resp.status == 200
            json_ref[:] = [2]
            resp = await self.session.get(self.url, json=json_ref)
            assert resp.status == 201
            json_ref[:] = [3]
            resp = await self.session.get(self.url, json=json_ref)
            assert resp.status == 202

            key = ("GET", URL(self.url))
            assert key in m.requests
            assert len(m.requests[key]) == 3
            assert m.requests[key][0].kwargs == {"allow_redirects": True, "json": [1]}
            assert m.requests[key][1].kwargs == {"allow_redirects": True, "json": [2]}
            assert m.requests[key][2].kwargs == {"allow_redirects": True, "json": [3]}

    async def test_request_with_non_deepcopyable_parameter(self) -> None:
        def non_deep_copyable():
            yield from ["header1,header2", "v1,v2", "v10,v20"]

        generator_value = non_deep_copyable()
        with aioresponses() as m:
            m.get(self.url, status=200)
            resp = await self.session.get(self.url, data=generator_value)
            assert resp.status == 200

            key = ("GET", URL(self.url))
            assert key in m.requests
            assert len(m.requests[key]) == 1
            assert m.requests[key][0].kwargs == {"allow_redirects": True, "data": generator_value}

    async def test_request_retrieval_in_case_no_response(self) -> None:
        with aioresponses() as m:
            with pytest.raises(ClientConnectionError):
                await self.session.get(self.url)

            key = ("GET", URL(self.url))
            assert key in m.requests
            assert len(m.requests[key]) == 1
            assert m.requests[key][0].args == ()
            assert m.requests[key][0].kwargs == {"allow_redirects": True}

    async def test_request_failure_in_case_session_is_closed(self) -> None:
        async def do_request(session: ClientSession) -> ClientResponse:
            return await session.get(self.url)

        with aioresponses():
            coro = do_request(self.session)
            await self.session.close()
            with pytest.raises(RuntimeError, match="Session is closed"):
                await coro

    async def test_address_as_instance_of_url_combined_with_pass_through(self) -> None:
        app = web.Application()

        async def handler_201(r: web.Request) -> web.Response:
            return web.Response(status=201)

        app.router.add_get("/status/201", handler_201)

        async with TestServer(app) as server:
            external_api = str(server.make_url("/status/201"))

            with aioresponses(passthrough=[external_api]) as m:
                m.get(self.url, status=200)
                api = await self.session.get(self.url)
                ext = await self.session.get(URL(external_api))

        assert api.status == 200
        assert ext.status == 201

    async def test_pass_through_with_origin_params(self) -> None:
        app = web.Application()

        async def handler_200(r: web.Request) -> web.Response:
            return web.Response(status=200)

        app.router.add_get("/get", handler_200)

        async with TestServer(app) as server:
            external_api = str(server.make_url("/get"))

            with aioresponses(passthrough=[external_api]):
                ext = await self.session.get(URL(external_api), params={"foo": "bar"})

        assert ext.status == 200
        assert "foo=bar" in str(ext.url)

    async def test_custom_response_class(self) -> None:
        class CustomClientResponse(ClientResponse):
            pass

        with aioresponses() as m:
            m.get(self.url, body="Test", response_class=CustomClientResponse)
            resp = await self.session.get(self.url)

        assert isinstance(resp, CustomClientResponse)

    async def test_request_should_match_regexp(self) -> None:
        with aioresponses() as mocked:
            mocked.get(re.compile(r"^http://example\.com/api\?foo=.*$"), payload={}, status=200)
            response = await self.request(self.url)
        assert response.status == 200

    async def test_request_does_not_match_regexp(self) -> None:
        with aioresponses() as mocked:
            mocked.get(re.compile(r"^http://exampleexample\.com/api\?foo=.*$"), payload={}, status=200)
            with pytest.raises(ClientConnectionError):
                await self.request(self.url)

    async def test_timeout(self) -> None:
        with aioresponses() as mocked:
            mocked.get(self.url, timeout=True)
            with pytest.raises(asyncio.TimeoutError):
                await self.request(self.url)

    async def test_callback(self) -> None:
        body = b"New body"
        captured: list[dict] = []

        def callback(url, **kwargs):
            assert str(url) == self.url
            captured.append(kwargs)
            return CallbackResult(body=body)

        with aioresponses() as m:
            m.get(self.url, callback=callback)
            response = await self.request(self.url)
            data = await response.read()

        assert data == body
        assert captured == [{"allow_redirects": True}]

    async def test_callback_coroutine(self) -> None:
        body = b"New body"
        event = asyncio.Event()

        async def callback(url, **kwargs):
            await event.wait()
            assert str(url) == self.url
            assert kwargs == {"allow_redirects": True}
            return CallbackResult(body=body)

        with aioresponses() as m:
            m.get(self.url, callback=callback)
            future = asyncio.ensure_future(self.request(self.url))
            await asyncio.sleep(0)  # let callback coroutine start and block at event.wait()
            assert not future.done()
            event.set()
            await asyncio.sleep(0)  # let callback complete
            assert future.done()
            response = future.result()
            data = await response.read()

        assert data == body

    async def test_callback_receives_json_kwarg(self) -> None:
        captured: list[dict] = []

        def callback(url, **kwargs):
            captured.append(kwargs)
            return CallbackResult(body=b"ok")

        with aioresponses() as m:
            m.post(self.url, callback=callback)
            await self.session.post(self.url, json={"x": 1, "y": "hello"})

        assert len(captured) == 1
        assert captured[0]["json"] == {"x": 1, "y": "hello"}

    async def test_callback_receives_data_kwarg(self) -> None:
        captured: list[dict] = []

        def callback(url, **kwargs):
            captured.append(kwargs)
            return CallbackResult(body=b"ok")

        with aioresponses() as m:
            m.post(self.url, callback=callback)
            await self.session.post(self.url, data=b"raw payload")

        assert len(captured) == 1
        assert captured[0]["data"] == b"raw payload"

    async def test_assert_not_called(self) -> None:
        with aioresponses() as m:
            m.get(self.url)
            m.assert_not_called()
            await self.session.get(self.url)
            with pytest.raises(AssertionError):
                m.assert_not_called()

    async def test_assert_called(self) -> None:
        with aioresponses() as m:
            m.get(self.url)
            with pytest.raises(AssertionError):
                m.assert_called()
            await self.session.get(self.url)

            m.assert_called_once()
            m.assert_called_once_with(self.url)
            m.assert_called_with(self.url)
            with pytest.raises(AssertionError):
                m.assert_not_called()
            with pytest.raises(AssertionError):
                m.assert_called_with("http://foo.bar")

    async def test_assert_called_twice(self) -> None:
        with aioresponses() as m:
            m.get(self.url, repeat=True)
            m.assert_not_called()
            await self.session.get(self.url)
            await self.session.get(self.url)
            with pytest.raises(AssertionError):
                m.assert_called_once()

    async def test_integer_repeat_once(self) -> None:
        with aioresponses() as m:
            m.get(self.url, repeat=1)
            m.assert_not_called()
            await self.session.get(self.url)
            with pytest.raises(ClientConnectionError):
                await self.session.get(self.url)

    async def test_integer_repeat_twice(self) -> None:
        with aioresponses() as m:
            m.get(self.url, repeat=2)
            m.assert_not_called()
            await self.session.get(self.url)
            await self.session.get(self.url)
            with pytest.raises(ClientConnectionError):
                await self.session.get(self.url)

    async def test_pattern_repeat_integer_exhausted(self) -> None:
        pattern = re.compile(r"^http://example\.com/api.*$")
        with aioresponses() as m:
            m.get(pattern, status=200, repeat=2)
            assert (await self.session.get(self.url)).status == 200
            assert (await self.session.get(self.url)).status == 200
            with pytest.raises(ClientConnectionError):
                await self.session.get(self.url)

    async def test_assert_any_call(self) -> None:
        http_bin_url = "http://httpbin.org"
        with aioresponses() as m:
            m.get(self.url)
            m.get(http_bin_url)
            await self.session.get(self.url)
            response = await self.session.get(http_bin_url)
            assert response.status == 200
            m.assert_any_call(self.url)
            m.assert_any_call(http_bin_url)

    async def test_assert_any_call_not_called(self) -> None:
        http_bin_url = "http://httpbin.org"
        with aioresponses() as m:
            m.get(self.url)
            response = await self.session.get(self.url)
            assert response.status == 200
            m.assert_any_call(self.url)
            with pytest.raises(AssertionError):
                m.assert_any_call(http_bin_url)

    async def test_assert_any_call_with_params(self) -> None:
        base_url = "http://example.com/search"
        full_url = "http://example.com/search?q=aiohttp"
        with aioresponses() as m:
            m.get(full_url, status=200)
            await self.session.get(base_url, params={"q": "aiohttp"})
            m.assert_any_call(base_url, params={"q": "aiohttp"})
            with pytest.raises(AssertionError):
                m.assert_any_call(base_url)

    async def test_exception_requests_are_tracked(self) -> None:
        with aioresponses() as mocked:
            kwargs = {"json": [42], "allow_redirects": True}
            mocked.get(self.url, exception=ValueError("oops"))
            with pytest.raises(ValueError):
                await self.session.get(self.url, **kwargs)

            key = ("GET", URL(self.url))
            requests = mocked.requests[key]
            assert len(requests) == 1
            assert requests[0].args == ()
            assert requests[0].kwargs == kwargs

    async def test_possible_race_condition(self) -> None:
        async def random_sleep_cb(url, **kwargs):
            await asyncio.sleep(uniform(0.01, 0.1))  # noqa: S311
            return CallbackResult(body="test")

        with aioresponses() as mocked:
            for i in range(20):
                mocked.get(f"http://example.org/id-{i}", callback=random_sleep_cb)

            tasks = [self.session.get(f"http://example.org/id-{i}") for i in range(20)]
            await asyncio.gather(*tasks)


class TestRaiseForStatusSession:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.url = "http://example.com/api?foo=bar#fragment"
        self.session = ClientSession(raise_for_status=True)
        yield
        await self.session.close()

    async def test_raise_for_status(self) -> None:
        with aioresponses() as m:
            m.get(self.url, status=400)
            with pytest.raises(ClientResponseError) as exc_info:
                await self.session.get(self.url)
        assert exc_info.value.message == http.RESPONSES[400][0]

    async def test_do_not_raise_for_status(self) -> None:
        with aioresponses() as m:
            m.get(self.url, status=400)
            response = await self.session.get(self.url, raise_for_status=False)
        assert response.status == 400

    @pytest.mark.skipif(
        Version("3.9.0") > AIOHTTP_VERSION,
        reason="aiohttp<3.9.0 does not support callable raise_for_status",
    )
    async def test_callable_raise_for_status(self) -> None:
        class CallableRaiseForStatusError(Exception):
            def __init__(self) -> None:
                super().__init__("callable raise_for_status")

        async def raise_for_status(response: ClientResponse) -> None:
            if response.status >= 400:
                raise CallableRaiseForStatusError

        with aioresponses() as m:
            m.get(self.url, status=400)
            with pytest.raises(Exception, match="callable raise_for_status"):
                await self.session.get(self.url, raise_for_status=raise_for_status)


class TestAIOResponseRedirect:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.url = "http://10.1.1.1:8080/redirect"
        self.session = ClientSession()
        yield
        await self.session.close()

    async def test_redirect_followed(self) -> None:
        with aioresponses() as rsps:
            rsps.get(self.url, status=307, headers={"Location": "https://httpbin.org"})
            rsps.get("https://httpbin.org")
            response = await self.session.get(self.url, allow_redirects=True)

        assert response.status == 200
        assert str(response.url) == "https://httpbin.org"
        assert len(response.history) == 1
        assert str(response.history[0].url) == self.url

    async def test_post_redirect_followed(self) -> None:
        with aioresponses() as rsps:
            rsps.post(self.url, status=307, headers={"Location": "https://httpbin.org"})
            rsps.get("https://httpbin.org")
            response = await self.session.post(self.url, allow_redirects=True)

        assert response.status == 200
        assert str(response.url) == "https://httpbin.org"
        assert response.method == "get"
        assert len(response.history) == 1
        assert str(response.history[0].url) == self.url

    async def test_redirect_missing_mocked_match(self) -> None:
        with aioresponses() as rsps:
            rsps.get(self.url, status=307, headers={"Location": "https://httpbin.org"})
            with pytest.raises(
                ClientConnectionError, match=re.escape("Connection refused: GET http://10.1.1.1:8080/redirect")
            ):
                await self.session.get(self.url, allow_redirects=True)

    async def test_redirect_missing_location_header(self) -> None:
        with aioresponses() as rsps:
            rsps.get(self.url, status=307)
            response = await self.session.get(self.url, allow_redirects=True)
        assert str(response.url) == self.url

    async def test_request_info(self) -> None:
        with aioresponses() as rsps:
            rsps.get(self.url, status=200)
            response = await self.session.get(self.url)

        request_info = response.request_info
        assert str(request_info.url) == self.url
        assert request_info.headers == {}

    async def test_request_info_with_original_request_headers(self) -> None:
        headers = {"Authorization": "Bearer access-token"}
        with aioresponses() as rsps:
            rsps.get(self.url, status=200)
            response = await self.session.get(self.url, headers=headers)

        request_info = response.request_info
        assert str(request_info.url) == self.url
        assert request_info.headers == headers

    async def test_relative_url_redirect_followed(self) -> None:
        base_url = "https://httpbin.org"
        url = f"{base_url}/foo/bar"
        with aioresponses() as rsps:
            rsps.get(url, status=307, headers={"Location": "../baz"})
            rsps.get(f"{base_url}/baz")
            response = await self.session.get(url, allow_redirects=True)

        assert response.status == 200
        assert str(response.url) == f"{base_url}/baz"
        assert len(response.history) == 1
        assert str(response.history[0].url) == url

    async def test_pass_through_unmatched_requests(self) -> None:
        app = web.Application()

        async def handler_200(r: web.Request) -> web.Response:
            return web.Response(status=200)

        app.router.add_get("/get", handler_200)

        async with TestServer(app) as server:
            matched_url = "https://matched_example.org"
            unmatched_url = str(server.make_url("/get"))

            with aioresponses(passthrough_unmatched=True) as m:
                m.post(URL(matched_url), status=200)
                mocked_response = await self.session.post(URL(matched_url))
                response = await self.session.get(URL(unmatched_url), params={"foo": "bar"})

        assert mocked_response.status == 200
        assert response.status == 200


class TestAIOResponsesAssertions:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.url = "http://example.com/api"
        self.session = ClientSession()
        yield
        await self.session.close()

    async def test_assert_called_with_json_match(self) -> None:
        with aioresponses() as m:
            m.post(self.url, status=200)
            await self.session.post(self.url, json={"key": "value", "count": 3})
            m.assert_called_with(
                self.url,
                method="POST",
                args_to_match=["json"],
                json={"key": "value", "count": 3},
            )

    async def test_assert_called_with_json_mismatch(self) -> None:
        with aioresponses() as m:
            m.post(self.url, status=200)
            await self.session.post(self.url, json={"key": "actual"})
            with pytest.raises(AssertionError):
                m.assert_called_with(
                    self.url,
                    method="POST",
                    args_to_match=["json"],
                    json={"key": "expected"},
                )

    async def test_assert_called_with_data_match(self) -> None:
        payload = b"raw request body"
        with aioresponses() as m:
            m.post(self.url, status=200)
            await self.session.post(self.url, data=payload)
            m.assert_called_with(
                self.url,
                method="POST",
                args_to_match=["data"],
                data=payload,
            )

    async def test_assert_called_with_data_mismatch(self) -> None:
        with aioresponses() as m:
            m.post(self.url, status=200)
            await self.session.post(self.url, data=b"actual body")
            with pytest.raises(AssertionError):
                m.assert_called_with(
                    self.url,
                    method="POST",
                    args_to_match=["data"],
                    data=b"expected body",
                )

    async def test_assert_called_with_headers_match(self) -> None:
        headers = {"X-Custom-Header": "test-value", "X-Request-Id": "abc123"}
        with aioresponses() as m:
            m.get(self.url, status=200)
            await self.session.get(self.url, headers=headers)
            m.assert_called_with(self.url, args_to_match=["headers"], headers=headers)

    async def test_assert_called_with_headers_mismatch(self) -> None:
        with aioresponses() as m:
            m.get(self.url, status=200)
            await self.session.get(self.url, headers={"X-Custom": "actual"})
            with pytest.raises(AssertionError):
                m.assert_called_with(
                    self.url,
                    args_to_match=["headers"],
                    headers={"X-Custom": "expected"},
                )

    async def test_assert_called_with_multiple_args_to_match(self) -> None:
        with aioresponses() as m:
            m.post(self.url, status=200)
            await self.session.post(self.url, json={"a": 1}, headers={"X-Trace": "xyz"})

            m.assert_called_with(
                self.url,
                method="POST",
                args_to_match=["json", "headers"],
                json={"a": 1},
                headers={"X-Trace": "xyz"},
            )
            with pytest.raises(AssertionError):
                m.assert_called_with(
                    self.url,
                    method="POST",
                    args_to_match=["json", "headers"],
                    json={"a": 1},
                    headers={"X-Trace": "wrong"},
                )

    async def test_assert_called_with_wrong_method(self) -> None:
        with aioresponses() as m:
            m.get(self.url, status=200)
            await self.session.get(self.url)
            with pytest.raises(AssertionError):
                m.assert_called_with(self.url, method="POST")

    async def test_assert_called_once_zero_requests(self) -> None:
        with aioresponses() as m:
            m.get(self.url, status=200)
            with pytest.raises(AssertionError):
                m.assert_called_once()

    async def test_assert_called_once_multiple_distinct_urls(self) -> None:
        other_url = "http://other.example.com/"
        with aioresponses() as m:
            m.get(self.url, status=200)
            m.get(other_url, status=200)
            await self.session.get(self.url)
            await self.session.get(other_url)
            with pytest.raises(AssertionError):
                m.assert_called_once()

    async def test_assert_not_called_message_reflects_request_count(self) -> None:
        with aioresponses() as m:
            m.get(self.url, exception=ValueError("boom"))
            with pytest.raises(ValueError):
                await self.session.get(self.url)
            with pytest.raises(AssertionError, match="Called 1"):
                m.assert_not_called()

    async def test_clear_preserves_requests(self) -> None:
        with aioresponses() as m:
            m.get(self.url, status=200)
            await self.session.get(self.url)

            key = ("GET", URL(self.url))
            assert key in m.requests
            assert len(m.requests[key]) == 1

            m.clear()

            assert m._matches == {}
            assert m._responses == []
            assert key in m.requests  # history is preserved
            assert len(m.requests[key]) == 1

    async def test_clear_then_re_register_serves_fresh_response(self) -> None:
        with aioresponses() as m:
            m.get(self.url, status=200)
            assert (await self.session.get(self.url)).status == 200

            m.clear()

            m.get(self.url, status=201)
            assert (await self.session.get(self.url)).status == 201
