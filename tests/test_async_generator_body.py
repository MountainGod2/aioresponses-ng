import pytest
from aiohttp import ClientSession

from aioresponses import aioresponses


@pytest.mark.asyncio
async def test_async_generator_body_exception():
    url = "http://1.2.3.4"
    with aioresponses() as m:
        m.post(url)

        class GeneratorNotAwaitedError(RuntimeError):
            def __init__(self):
                super().__init__("this generator is never awaited")

        async def data_generator():
            yield b"foo"
            raise GeneratorNotAwaitedError()

        with pytest.raises(RuntimeError, match="never awaited"):
            async with ClientSession() as session:
                async with session.post(url, data=data_generator()) as resp:
                    await resp.text()
