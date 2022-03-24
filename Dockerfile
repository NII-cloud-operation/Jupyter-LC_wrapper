FROM jupyter/scipy-notebook

# LC_wrapper test container

USER root

## configurations
RUN mkdir -p /tmp/kernels/python3-wrapper /tmp/wrapper-kernels/python3 && \
    echo '{"display_name":"Python 3 (LC_wrapper)","language":"python","argv":["/opt/conda/bin/python","-m","lc_wrapper","--debug","-f","{connection_file}"]}' > /tmp/kernels/python3-wrapper/kernel.json && \
    echo '{"display_name":"Python 3","language":"python","argv":["/opt/conda/bin/python","-m","lc_wrapper","--debug","-f","{connection_file}"]}' > /tmp/wrapper-kernels/python3/kernel.json

RUN echo "c.MultiKernelManager.kernel_manager_class = 'lc_wrapper.LCWrapperKernelManager'" > $CONDA_DIR/etc/jupyter/jupyter_notebook_config.py && \
    echo "c.KernelManager.shutdown_wait_time = 10.0" >> $CONDA_DIR/etc/jupyter/jupyter_notebook_config.py && \
    echo "c.NotebookApp.kernel_spec_manager_class = 'lc_wrapper.LCWrapperKernelSpecManager'" >> $CONDA_DIR/etc/jupyter/jupyter_notebook_config.py

## install
COPY . /tmp/wrapper
RUN pip --no-cache-dir install /tmp/wrapper

RUN jupyter kernelspec install /tmp/kernels/python3-wrapper --sys-prefix && \
    jupyter wrapper-kernelspec install /tmp/wrapper-kernels/python3 --sys-prefix && \
    fix-permissions /home/$NB_USER

USER $NB_USER
