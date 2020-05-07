"""Wrapper Kernel for Literate Computing"""

from .kernel import LCWrapperKernelManager
from .kernelspec import LCWrapperKernelSpecManager

try:
    # import async kernel manager if jupyter_client>=6.1.0 and Python3
    from ipython_genutils.py3compat import PY3
    if PY3:
        from .async_kernelmanager import AsyncLCWrapperKernelManager
except ImportError:
    pass

# nbextension
def _jupyter_nbextension_paths():
    return [dict(
        section="notebook",
        src="nbextension",
        dest="lc_wrapper",
        require="lc_wrapper/main")]
