import asyncio


def avait(coro):
    loop = asyncio.get_event_loop()
    task = asyncio.ensure_future(coro)
    return loop.run_until_complete(task)


def asynchronize(coro):
    def sync_fun(*args, **kwargs):
        return avait(coro(*args, **kwargs))
    return sync_fun
