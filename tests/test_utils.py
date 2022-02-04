import inspect
from lc_wrapper import utils


def test_run_sync_with_normal_func():
    def func():
        return 'executed'
    v = utils.run_sync(func())
    assert v == 'executed'

def test_run_sync_with_async_func():
    async def func_async():
        return 'async-executed'
    v = utils.run_sync(func_async())
    assert v == 'async-executed'
