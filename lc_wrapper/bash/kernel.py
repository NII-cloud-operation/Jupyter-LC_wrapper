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

