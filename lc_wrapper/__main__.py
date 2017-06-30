from ipykernel.kernelapp import IPKernelApp
from . import PythonKernelBuffered

IPKernelApp.launch_instance(kernel_class=PythonKernelBuffered)
