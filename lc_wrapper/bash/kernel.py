import sys
from ast import literal_eval
from ipython_genutils.py3compat import PY3

from ..kernel import BufferedKernelBase

class BashKernelBuffered(BufferedKernelBase):
    implementation = 'Literate Computing Wrapper Kernel(Bash)'
    implementation_version = '0.1'
    language = 'bash'
    language_version = '0.1'
    language_info = {
        'name': 'bash'
    }
    banner = 'Literate Computing Wrapper Kernel(Bash)'

    def _get_wrapped_kernel_name(self):
        return 'bash'

    def _get_env_request(self, client):
        result = self.send_code_to_ipython_kernel(client, 'env')
        self.log.debug('_get_env_request: {}'.format(result))
        return dict([self._parse_env(l.strip()) \
                     for l in result.split('\n') if len(l.strip()) > 0])

    def _parse_env(self, line):
        if '=' in line:
            pos = line.index('=')
            return (line[:pos], line[pos + 1:])
        else:
            return (line, '')
