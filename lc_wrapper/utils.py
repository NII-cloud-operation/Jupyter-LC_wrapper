import asyncio
import inspect
from IPython.core.async_helpers import get_asyncio_loop


def run_sync(maybe_future):
    if not inspect.isawaitable(maybe_future):
        return maybe_future
    loop = get_asyncio_loop()
    future = asyncio.ensure_future(maybe_future, loop=loop)
    try:
        return loop.run_until_complete(future)
    except BaseException as e:
        future.cancel()
        raise e
