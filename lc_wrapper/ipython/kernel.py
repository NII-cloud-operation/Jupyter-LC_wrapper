import sys
from ast import literal_eval
from ipython_genutils.py3compat import PY3

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
        'pygments_lexer': 'ipython%d' % (3 if PY3 else 2),
        'nbconvert_exporter': 'python',
        'file_extension': '.py'
    }
    banner = 'Literate Computing Wrapper Kernel(IPython)'

    def _get_wrapped_kernel_name(self):
        return 'python3' if PY3 else 'python2'

    def _get_env_request(self, client):
        result = self.send_code_to_ipython_kernel(client, '%env')
        self.log.debug('_get_env_request: {}'.format(result))
        return literal_eval(result)
