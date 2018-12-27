"""Wrapper Kernel for Literate Computing"""

from .kernel import LCWrapperKernelManager

# nbextension
def _jupyter_nbextension_paths():
    return [dict(
        section="notebook",
        src="nbextension",
        dest="lc_wrapper",
        require="lc_wrapper/main")]
