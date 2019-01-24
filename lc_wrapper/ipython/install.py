import argparse
import json
import os
import sys

from ipython_genutils.py3compat import PY3
from jupyter_client.kernelspec import KernelSpecManager
from IPython.utils.tempdir import TemporaryDirectory

from ..kernelspec import LCWrapperKernelSpecManager

wrapper_kernel_json = {
    "argv": [sys.executable, "-m", "lc_wrapper.ipython", "-f", "{connection_file}"],
    "display_name": "LC_wrapper",
    "language": "python"
}

kernel_json = {
    "argv": [sys.executable, "-m", "lc_wrapper.ipython", "-f", "{connection_file}"],
    "display_name": 'Python %i' % sys.version_info[0],
    "language": "python"
}


def install_my_kernel_spec(name, kernel_json, user=True, prefix=None,
                           kernelspec_manager_class=KernelSpecManager):
    with TemporaryDirectory() as td:
        os.chmod(td, 0o755) # Starts off as 700, not user readable
        with open(os.path.join(td, 'kernel.json'), 'w') as f:
            json.dump(kernel_json, f, sort_keys=True)

        kernelspec_manager = kernelspec_manager_class()
        kernelspec_manager.install_kernel_spec(td,
                                               name,
                                               user=user,
                                               replace=True,
                                               prefix=prefix)

def _is_root():
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False # assume not an admin on non-Unix platforms

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--user', action='store_true',
        help="Install to the per-user kernels registry. Default if not root.")
    ap.add_argument('--sys-prefix', action='store_true',
        help="Install to sys.prefix (e.g. a virtualenv or conda env)")
    ap.add_argument('--prefix',
        help="Install to the given prefix. "
             "Kernelspec will be installed in {PREFIX}/share/jupyter/kernels/")
    args = ap.parse_args(argv)

    if args.sys_prefix:
        args.prefix = sys.prefix
    if not args.prefix and not _is_root():
        args.user = True

    print('Installing Jupyter kernel spec')
    install_my_kernel_spec('lc_wrapper', wrapper_kernel_json,
                           user=args.user, prefix=args.prefix,
                           kernelspec_manager_class=KernelSpecManager)
    install_my_kernel_spec('python3' if PY3 else 'python2', kernel_json,
                           user=args.user, prefix=args.prefix,
                           kernelspec_manager_class=LCWrapperKernelSpecManager)

if __name__ == '__main__':
    main()
