![demo](./demo.gif)

# Jupyter-LC_wrapper

  Jupyter-LC_wrapper, we call lc_wrapper, is a wrapper kernel that relay the code and messages between the ipython kernel and the notebook server.
  The original ipython kernel is hard to use at the time of huge output. The behavior of the browser slows down, and it stops working at the worst. The lc_wrapper resolved this difficulty by summarizing the data sent to the notebook server.  
The lc_wrapper has several features shown below:

* Turn on and off this features easily.
* It is summarized that the contents displayed on the output area of the notebook.
* The specified keywords can be checked.
* The output results are saved in the files with the executed history.

## Prerequisite

* Jupyter Notebook 4.2.x
* Python2.7
* (Optional) Jupyter-LC_nblineage and Jupyter-multi_outputs ... to track relation between output file and cell (MEME)

## How to Install
#### Install Jupyter-LC_wrapper

To install `lc_wrapper` by pip:

```
pip install git+https://github.com/NII-cloud-operation/Jupyter-LC_wrapper
python -m lc_wrapper.ipython.install
```

If you'd like to use with [bash kernel](https://github.com/takluyver/bash_kernel), you can install lc_wrapper for bash kernel as follows:

```
python -m lc_wrapper.bash.install
```

#### Install Jupyter-LC_nblineage and Jupyter-multi_outputs

In order to save output files with cell MEMEs, you should install and enable Jupyter-LC_nblineage and Jupyter-multi_outputs.

- Jupyter-LC_nblineage ... See [Jupyter-LC_nblineage/README](https://github.com/NII-cloud-operation/Jupyter-LC_nblineage#installation)
- Jupyter-multi_outputs ... See [Jupyter-multi_outputs/README](https://github.com/NII-cloud-operation/Jupyter-multi_outputs#how-to-install)

#### Install and enable frontend extension

Jupyter-LC_wrapper has the frontend extension for recording log file history as cell metadata.

To install the extension, copy its files into the jupyter server's search directory.

```
jupyter nbextension install --py lc_wrapper --user
```

To use the extension, you will also need to enable it.

```
jupyter nbextension enable --py lc_wrapper --user
```

#### Replace KernelManager

Replace KernelManager for customized `shutdown_kernel()` behavior.

Append the below line to `jupyter_notebook_config.py`.

```
c.MultiKernelManager.kernel_manager_class = 'lc_wrapper.LCWrapperKernelManager'
```

#### Replace KernelSpecManager (optional)

If you want to completely replace the Python or Bash kernel in the kernel selection list with the wrapper kernel,
you can use the custom kernel spec manager (`lc_wrapper.LCWrapperKernelSpecManager`).
This custom kernel spec manager provides another kernel spec list that is separated from the default kernel spec list.

Append the following line to `jupyter_notebook_config.py`

```
c.NotebookApp.kernel_spec_manager_class = 'lc_wrapper.LCWrapperKernelSpecManager'
```

If you want to install additional kernels to this kernel spec list,
you can use `jupyter wrapper-kernelspec` command like `jupyter kernelspec` command.
For details, please execute `jupyter wrapper-kernelspec --help`.

## How to Use

### Logging cell output

The Jupyter-LC_wrapper kernel logs the cell output to a local file for each execution.
The frontend extension records the log file path as cell metadata.
The log file path is sent to the frontend with `execute_reply` message.

Example of cell metadata:
```
{
  "lc_wrapper": {
    "log_history": [
      "/notebooks/.log/20181221/20181221-141855-0874.log",
      "/notebooks/.log/20181221/20181221-141912-0312.log"
    ]
  },
  (snip)
}
```

### Enabling Summarizing mode

To use the summarizing mode, you should make the code cell with `!!` at the beginning of the command.

```
Example:  

[In]
---
!!1+1

[In]
---
!!!ls -al
```

Also you can use `lc_wrapper_force` environment variable to enable/disable the mode forcefully on every cell.

```
[In]
---
%env lc_wrapper_force=on

[In]
---
# The summarizing mode enabled without `!!`
!ls
```

### Settings by Environment Variables

* Control the output area with the environment variable 'lc_wrapper'.

```
%env lc_wrapper=s:h:e:f  
s : Summary starts when # of output lines exceed 's' (default s=50)
h : Summary displays the first h lines and max 2 x h error lines. (default h=20)
e : Max # of output lines in progress. (default e=1)
f : Summary displays the last f lines (default f=20)

Example:  

[In]
---
%env lc_wrapper=2:2:2:2

[In]
---
!!from time import sleep
for i in xrange(10):
    print i
    sleep(0.5)

[Out]
---
start time: 2017-04-26 14:00:51(JST)
end time: 2017-04-26 14:00:56(JST)
Output Size(byte): 237, Lines: 18, Path: /notebooks/.log/20170426/20170426-140052-0662.log
0 keyword matched or stderr happened

0
1
...
8
9

```

* Manage a history of the output with the environment variable 'lc_wrapper_uuid'.

```
%env lc_wrapper_uuid=x
x : a character string that does not conflict with other uuid.
If Jupyter-multi_outputs and Jupyter-LC_nblineage are installed and turned on, uuid is set automatically.
When both lc_wrapper_uuid and Jupyter-LC_nblineage's uuid are set, lc_wrapper_uuid takes precedence.

Example:  

[In]
---
%env lc_wrapper_uuid=857ade64-e4fe-4bcf-b46f-ac190ce44c44

[In]
---
!!from time import sleep
for i in xrange(10):
    print i
    sleep(0.5)

[Out]
---
start:2017-04-26 13:59:49(JST)
end:2017-04-26 13:59:54(JST)
path:/notebooks/.log/20170426/20170426-135950-0120.log

start:2017-04-26 14:00:51(JST)
end:2017-04-26 14:00:56(JST)
path:/notebooks/.log/20170426/20170426-140052-0662.log

start time: 2017-04-26 14:20:37(JST)
end time: 2017-04-26 14:20:42(JST)
Output Size(byte): 305, Lines: 18, Path: /notebooks/.log/20170426/20170426-142038-0557.log
0 keyword matched or stderr happened

0
1
...
8
9
```

* Check the keywords with the environment variable 'lc_wrapper_regex'.

```
%env lc_wrapper_regex=y
y = keywords : If check two words word1 and word2, write with a separator '|' such as y = word1|word2.
y = file:filename : If use regular expression, write with a suffix 'file:' such as y = file:xxxxx.txt.
The file will be saved in the same directory as notebooks.
In the file, one regular expression can be written on one line, and multiple lines can be described.


Example:  

[In]
---
%env lc_wrapper_regex=3|5|7

[In]
---
!!from time import sleep
for i in xrange(10):
    print i
    sleep(0.5)

[Out]
---
start:2017-04-25 14:21:31(JST)
end:2017-04-25 14:21:37(JST)
path:/notebooks/.log/20170425/20170425-142133-0179.log

start:2017-04-25 14:21:37(JST)
end:2017-04-25 14:21:42(JST)
path:/notebooks/.log/20170425/20170425-142139-0169.log

start:2017-04-25 14:21:48(JST)
end:2017-04-25 14:21:53(JST)
path:/notebooks/.log/20170425/20170425-142149-0683.log

start:2017-04-26 14:35:17(JST)
end:2017-04-26 14:35:22(JST)
path:/notebooks/.log/20170426/20170426-143517-0955.log

start time: 2017-04-26 14:39:13(JST)
end time: 2017-04-26 14:39:18(JST)
Output Size(byte): 189, Lines: 16, Path: /notebooks/.log/20170426/20170426-143915-0070.log
3 keyword matched or stderr happened

0
1
...
3
5
7
...
8
9
```

### Settings by configuration file

You can apply the settings to multiple notebooks using `.lc_wrapper` configuration file in the notebook directory as follows:

```
# Example of .lc_wrapper
lc_wrapper_force=on
lc_wrapper=2:2:2:2
lc_wrapper_regex=3|5|7
```

If you set both the configuration file and environment variables, the environment variables are applied and the duplicated entries in the configuration file are ignored.


## License

This project is licensed under the terms of the Modified BSD License (also known as New or Revised or 3-Clause BSD), see LICENSE.txt.
