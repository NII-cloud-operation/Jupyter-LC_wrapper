import os.path

from jupyter_core.paths import jupyter_path, SYSTEM_JUPYTER_PATH
from jupyter_client.kernelspec import KernelSpecManager


class LCWrapperKernelSpecManager(KernelSpecManager):

    def _user_kernel_dir_default(self):
        return os.path.join(self.data_dir, 'lc_wrapper_kernels')

    def _kernel_dirs_default(self):
        return jupyter_path('lc_wrapper_kernels')

    def _ensure_native_kernel_default(self):
        return False

    def _get_destination_dir(self, kernel_name, user=False, prefix=None):
        if user:
            return os.path.join(self.user_kernel_dir, kernel_name)
        elif prefix:
            return os.path.join(os.path.abspath(prefix),
                                'share', 'jupyter', 'lc_wrapper_kernels',
                                kernel_name)
        else:
            return os.path.join(SYSTEM_JUPYTER_PATH[0],
                                'lc_wrapper_kernels',
                                kernel_name)
