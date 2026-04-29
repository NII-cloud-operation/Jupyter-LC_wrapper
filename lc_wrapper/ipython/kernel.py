import sys

from ..kernel import BufferedKernelBase

class PythonKernelBuffered(BufferedKernelBase):
    implementation = 'Literate Computing Wrapper Kernel(IPython)'
    implementation_version = '0.1'
    language = 'python'
    language_version = '0.1'
    language_info = {
        'name': 'python',
        'version': sys.version.split()[0],
        'mimetype': 'text/x-python',
        'pygments_lexer': 'ipython3',
        'nbconvert_exporter': 'python',
        'file_extension': '.py'
    }
    banner = 'Literate Computing Wrapper Kernel(IPython)'

    def _get_wrapped_kernel_name(self):
        return 'python3'
