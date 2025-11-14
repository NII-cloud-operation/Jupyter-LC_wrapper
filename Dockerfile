FROM quay.io/jupyter/scipy-notebook:notebook-7.4.7

USER root

# Install Node.js 20.x (required for nblineage build)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    mkdir -p /.npm && \
    chown jovyan:users -R /.npm && \
    rm -rf /var/lib/apt/lists/*
ENV NPM_CONFIG_PREFIX=/.npm
ENV PATH=/.npm/bin/:${PATH}

## install lc_wrapper
COPY . /tmp/wrapper
RUN pip --no-cache-dir install /tmp/wrapper

# Workaround for https://github.com/NII-cloud-operation/Jupyter-LC_wrapper/issues/71
RUN pip install --upgrade jupyter_core==5.6.1

# Install nblineage
RUN pip install --no-cache git+https://github.com/NII-cloud-operation/Jupyter-LC_nblineage.git

## configurations
RUN mkdir -p /tmp/kernels/python3-wrapper /tmp/wrapper-kernels/python3 && \
    echo '{"display_name":"Python 3 (LC_wrapper)","language":"python","argv":["/opt/conda/bin/python","-m","lc_wrapper","--debug","-f","{connection_file}"]}' > /tmp/kernels/python3-wrapper/kernel.json && \
    echo '{"display_name":"Python 3","language":"python","argv":["/opt/conda/bin/python","-m","lc_wrapper","--debug","-f","{connection_file}"]}' > /tmp/wrapper-kernels/python3/kernel.json

RUN echo "c.MultiKernelManager.kernel_manager_class = 'lc_wrapper.LCWrapperKernelManager'" > $CONDA_DIR/etc/jupyter/jupyter_notebook_config.py && \
    echo "c.KernelManager.shutdown_wait_time = 10.0" >> $CONDA_DIR/etc/jupyter/jupyter_notebook_config.py && \
    echo "c.NotebookApp.kernel_spec_manager_class = 'lc_wrapper.LCWrapperKernelSpecManager'" >> $CONDA_DIR/etc/jupyter/jupyter_notebook_config.py

RUN jupyter labextension enable lc_wrapper && \
    jupyter kernelspec install /tmp/kernels/python3-wrapper --sys-prefix && \
    jupyter wrapper-kernelspec install /tmp/wrapper-kernels/python3 --sys-prefix && \
    fix-permissions /home/$NB_USER

USER $NB_USER

RUN jupyter nblineage quick-setup --user
