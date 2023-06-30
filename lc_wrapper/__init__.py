"""Wrapper Kernel for Literate Computing"""

from .kernel import LCWrapperKernelManager
from .kernelspec import LCWrapperKernelSpecManager
from .async_kernelmanager import AsyncLCWrapperKernelManager

# nbextension
def _jupyter_nbextension_paths():
    return [dict(
        section="notebook",
        src="nbextension",
        dest="lc_wrapper",
        require="lc_wrapper/main")]
