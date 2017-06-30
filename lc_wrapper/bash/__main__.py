from ipykernel.kernelapp import IPKernelApp
from . import BashKernelBuffered

IPKernelApp.launch_instance(kernel_class=BashKernelBuffered)
