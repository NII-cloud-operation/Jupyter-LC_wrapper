from traitlets import Instance, Dict
from jupyter_client.kernelspecapp import (ListKernelSpecs,
                                          InstallKernelSpec,
                                          RemoveKernelSpec,
                                          KernelSpecApp)
from .kernelspec import LCWrapperKernelSpecManager


class LCWrapperListKernelSpecs(ListKernelSpecs):
    kernel_spec_manager = Instance(LCWrapperKernelSpecManager)

    def _kernel_spec_manager_default(self):
        return LCWrapperKernelSpecManager(parent=self, data_dir=self.data_dir)


class LCWrapperInstallKernelSpec(InstallKernelSpec):
    kernel_spec_manager = Instance(LCWrapperKernelSpecManager)

    def _kernel_spec_manager_default(self):
        return LCWrapperKernelSpecManager(parent=self, data_dir=self.data_dir)


class LCWrapperRemoveKernelSpec(RemoveKernelSpec):
    kernel_spec_manager = Instance(LCWrapperKernelSpecManager)

    def _kernel_spec_manager_default(self):
        return LCWrapperKernelSpecManager(parent=self, data_dir=self.data_dir)


class LCWrapperKernelSpecApp(KernelSpecApp):
    subcommands = Dict({
        'list':      (LCWrapperListKernelSpecs,
                      ListKernelSpecs.description.splitlines()[0]),
        'install':   (LCWrapperInstallKernelSpec,
                      InstallKernelSpec.description.splitlines()[0]),
        'uninstall': (LCWrapperRemoveKernelSpec,
                      "Alias for remove"),
        'remove':    (LCWrapperRemoveKernelSpec,
                      RemoveKernelSpec.description.splitlines()[0]),
    })


if __name__ == '__main__':
    LCWrapperKernelSpecApp.launch_instance()
