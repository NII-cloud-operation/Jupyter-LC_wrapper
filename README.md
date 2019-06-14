![demo](./demo.gif)

# Jupyter-LC_wrapper

  Jupyter-LC_wrapper, we call lc_wrapper, is a wrapper kernel that relay the code and messages between the ipython kernel and the notebook server.
  The original ipython kernel is hard to use at the time of huge output. The behavior of the browser slows down, and it stops working at the worst. The lc_wrapper resolved this difficulty by summarizing the data sent to the notebook server.  
The lc_wrapper has several features shown below:

* Turn on and off this features easily.
* It is summarized that the contents displayed on the output area of the notebook.
* The specified keywords can be checked.
* The output results are saved in the files with the executed history.
* Secrets words that specified by "pattern regexp" are masked with '***...'.

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

The log directory named `.log` is created in the current working directory (the same directory as the notebook file).
If this directory is not writable, the `.log` directory is created in the your home directory.

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

### Settings by configuration file

You can customize the summarizing settings by creating a configuration file
named `.lc_wrapper`.
The Jupyter-LC_wrapper searches the configuration file in the following order
and reads the first file found.

1. Current working directory (the same directory as the notebook file)
2. Home directory (`~/.lc_wrapper`)

The configuration file is a text file consisting of lines like `key=value`.
If the line is empty or starts with `#`, it is ignored.

This is an example of `.lc_wrapper` file.

```
# Example of .lc_wrapper
lc_wrapper_force=on
lc_wrapper=2:2:2:2
lc_wrapper_regex=3|5|7
lc_wrapper_masking_pattern=(?:[0-9]{11}@[a-z]*.proxy.example.com:8080)|AKIAJTQHFTLP426OCK3Q|2468
lc_wrapper_mask_log=on
```

#### `lc_wrapper_force`

You can use `lc_wrapper_force` to enable summarizing mode forcefully on every cell.

If the value is `on`, summarizing mode is enabled on every cell.
If it is `off` or otherwise, the enable/disable of the summarizing mode follows the contents of the cell.

If it is enabled, even if the code cell does not start with `!!`, the output is summarized.

#### `lc_wrapper`

The `lc_wrapper` controls the summarized output.

The meaning of value is as follows.

`lc_wrapper=s:h:e:f`

* `s` : Summary starts when # of output lines exceed 's' (default s=50)
* `h` : Summary displays the first h lines and max 2 x h error lines. (default h=20)
* `e` : Max # of output lines in progress. (default e=1)
* `f` : Summary displays the last f lines (default f=20)

The following is an example of code and output for `lc_wrapper=2:2:2:2`.

```
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

#### `lc_wrapper_regex`

The `lc_wrapper_regex` is a regular expression for finding error message lines from the output to display in the summarized output.

If the value starts with `file:` such as `file:xxxx.txt`,
the wrapper kernel interprets the part after `file:` as a filename in the same directory as a notebook file,
read its contents as regular expressions.
In this file, one regular expression can be written on one line, and multiple lines can be described.

If the filename part is `default`, it means the default regular expressions file named `.lc_wrapper_regex.txt`.
The Jupyter-LC_wrapper searches `.lc_wrapper_regex.txt` in the following order and reads the first file found.

1. Current working directory (the same directory as the notebook file)
2. Home directory (`~/.lc_wrapper_regex.txt`)

The default value of `lc_wrapper_regex` is `file:default`.

If the default regular expressions file is not found, the wrapper kernel generates a file with default contents.

The following is an example of code and output for `lc_wrapper_regex=3|5|7`.

```
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

#### `lc_wrapper_masking_pattern`

Mask the keywords of the output and log file with variable 'lc_wrapper_masking_pattern'.
 
The meaning of value is as follows.

```
lc_wrapper_masking_pattern=z
z is a regular expression to mask. Ex.) pass_word|[0-9a-zA-Z_]+@[0-9a-zA-Z.]+?com|AKIAIOSFODNN7EXAMPLE .
```

Example1: `lc_wrapper_masking_pattern=home|123`

```
[In]
---
!!print("home is 123")

[Out]
---
path: /notebooks/.log/20181127/20181127-032445-0875.log (2 logs recorded)
start time: 2018-11-27 03:24:45(UTC)
end time: 2018-11-27 03:24:45(UTC)
output size: 474 bytes
0 chunks with matched keywords or errors
----
**** is ***
```

Example2: `lc_wrapper_masking_pattern=home|abc|[0-9a-zA-Z_]+@[0-9a-zA-Z.]+?com`

```
[In]
---
!!print("home,123,jamine_wewe@163.com")

[Out]
---
path: /notebooks/.log/20181127/20181127-054528-0906.log (9 logs recorded)
start time: 2018-11-27 05:45:28(UTC)
end time: 2018-11-27 05:45:28(UTC)
output size: 494 bytes
0 chunks with matched keywords or errors
----
****,123,*******************
```

#### `lc_wrapper_mask_log`

When value is `on`, mask the secret words (strings that matches to lc_wrapper_masking_pattern) with "***..." in the log file. 

And when it is `off` or otherwise,  strings in log files are not masked. 

default value is `on`.

### Settings by environment variables

Instead of the configuration file, you can set with the environment variables.

For example, set the environment variables as follows.

```
$ export lc_wrapper_force='on'
$ export lc_wrapper='2:2:2:2'
$ export lc_wrapper_regex='3|5|7'
$ export lc_wrapper_masking_pattern='[0-9a-zA-Z_]+@[0-9a-zA-Z.]+?com'
$ export lc_wrapper_mask_log=off
```

The name of environemnt variable is same to the key name of the configuration file.

If you set both the configuration file and environment variables, the environment variables are applied and the duplicated entries in the configuration file are ignored.

## License

This project is licensed under the terms of the Modified BSD License (also known as New or Revised or 3-Clause BSD), see LICENSE.txt.
