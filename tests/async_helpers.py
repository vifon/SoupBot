from functools import wraps
import asyncio


def avait(coro):
    """Emulate await in a synchronous function."""
    loop = asyncio.get_event_loop()
    task = asyncio.ensure_future(coro)
    return loop.run_until_complete(task)


def asynchronize(coro):
    """Turn an asynchronous function into a synchronous one.

    Useful for test frameworks that don't support async tests when the
    tested functions are async.

    """
    @wraps(coro)
    def sync_fun(*args, **kwargs):
        return avait(coro(*args, **kwargs))
    return sync_fun
