import os

from setuptools import setup

HERE = os.path.abspath(os.path.dirname(__file__))
VERSION_NS = {}
with open(os.path.join(HERE, 'lc_wrapper', '_version.py')) as f:
    exec(f.read(), {}, VERSION_NS)

setup(
    name='lc_wrapper',
    version=VERSION_NS['__version__'],
    packages=['lc_wrapper', 'lc_wrapper.ipython', 'lc_wrapper.bash'],
    install_requires=[
        'ipykernel>=4.0.0',
        'ipython>=8.0.0',
        'jupyter_client!=7.0.0,!=7.0.1,!=7.0.2,!=7.0.3',
        'python-dateutil',
        'fluent-logger'
    ],
    description='Kernel Wrapper for Literate Computing',
    author='NII Cloud Operation Team',
    url='https://github.com/NII-cloud-operation/',
    include_package_data=True,
    zip_safe=False,
    entry_points = {
        'console_scripts': [
            'jupyter-wrapper-kernelspec = lc_wrapper.kernelspecapp:LCWrapperKernelSpecApp.launch_instance'
        ]
    }
)
