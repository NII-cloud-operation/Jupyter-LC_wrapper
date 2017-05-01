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
* (Option) Jupyter-LC_nblineage 

## How to Install
#### Install Jupyter-LC_wrapper

* Make lc_wrapper directory under jupyter/kernels
```
  mkdir ~/.local/share/jupyter/kernels/lc_wrapper
```
* Copy kernel.json
```
  cp kernel.json ~/.local/share/jupyter/kernels/lc_wrapper/
```
* Copy lc_wrapper.py
```
  cp lc_wrapper.py /usr/local/lib/python2.7/dist-packages/
```
* Reboot notebook server

#### Install lc_CodeCell_execute (and Jupyter-LC_nblineage)

```
jupyter nbextension install lc_CodeCell_execute --user
jupyter nbextension enable lc_CodeCell_execute/main --user
```
#### Patch for KernelManager
* Patch to shutdown_kernel() in /jupyter_client/manager.py
```
@@ -315,6 +315,8 @@ class KernelManager(ConnectionFileMixin)
         # Stop monitoring for restarting while we shutdown.
         self.stop_restarter()
 
+        self.interrupt_kernel()
+        time.sleep(5.0)
         if now:
             self._kill_kernel()
         else:
```


## How to Use

* Execute the code cell with '!!' at the beginning of the command.

```
Example:  

[In]
---
!!1+1

[In]
---
!!!ls -al
```
* Control the output area with the environment variable 'lc_wrapper'.

```
%env lc_wrapper=s:h:e:f  
s : Number of lines before the summary function starts. (default s=1)
h : Number of lines at the head of the output. (default h=1)
e : Maximum number of lines of messages sent in one stream. (default e=1)
f : Number of lines at the tail of the output. (default f=1)

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
If lc_CodeCell_execute and Jupyter-LC_nblineage are installed and turned on, uuid is set automatically.
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



## License

This project is licensed under the terms of the Modified BSD License (also known as New or Revised or 3-Clause BSD), see LICENSE.txt.
