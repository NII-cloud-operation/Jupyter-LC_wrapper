from __future__ import print_function

from functools import partial
try:
    from queue import Empty  # Python 3
except ImportError:
    from Queue import Empty  # Python 2
import sys
import time
import zmq
try:
    monotonic = time.monotonic
except AttributeError:
    # py2
    monotonic = time.time  # close enough

try:
    TimeoutError
except NameError:
    # py2
    TimeoutError = RuntimeError

from ipykernel.kernelbase import Kernel
from datetime import datetime, timedelta
import os
import os.path
from ipython_genutils.py3compat import PY3
from jupyter_client.multikernelmanager import MultiKernelManager
from jupyter_client.ioloop import IOLoopKernelManager
from jupyter_core.paths import jupyter_runtime_dir
import re
import json
import threading


SUMMARIZE_KEY = 'lc_wrapper'
ENV_LOG_HISTORY_KEY = 'lc_wrapper_uuid'
IGNORE_SUMMARIZE_KEY = 'lc_wrapper_regex'
LOG_HISTORY_KEY_LEVEL1 = 'lc_cell_data'
LOG_HISTORY_KEY_LEVEL2 = 'lc_cell_meme'

IPYTHON_DEFAULT_PATTERN_FILE = 'lc_wrapper_regex.txt'
IPYTHON_DEFAULT_PATTERN = '''ERROR|error|Error|Panic|panic|Invalid|invalid|Warning|warning|Bad|bad
(Not|not) (Found|found)
(Device)? not ready
out of (Memory|memory)
interrupt(ed)?|abort(ed)?|stop(ped)?
insecure|inaccessible|Forbidden|forbidden|Denied|denied
Unauthorised|unauthorised|Unauthorized|unauthorized
(No|no|Low|low) (.+ )?(Capacity|capacity|Space|space)
has (encountered|stopped)'''


def getfilesystemencoding():
    encoding = sys.getfilesystemencoding()
    if encoding is None:
        encoding = sys.getdefaultencoding()
    return encoding


class PythonKernelBuffered(Kernel):
    implementation = 'Literate Computing Wrapper Kernel'
    implementation_version = '1.0'
    language = 'python'
    language_version = '0.1'
    language_info = {
        'name': 'python',
        'version': sys.version.split()[0],
        'mimetype': 'text/x-python',
        'pygments_lexer': 'ipython%d' % (3 if PY3 else 2),
        'nbconvert_exporter': 'python',
        'file_extension': '.py'
    }
    banner = 'Literate Computing Wrapper Kernel'

    def __init__(self, **kwargs):
        Kernel.__init__(self, **kwargs)
        self.start_ipython_kernel()

    def start_ipython_kernel(self):
        self.km = MultiKernelManager()
        self.km.connection_dir = jupyter_runtime_dir()
        self.kernelid = self.km.start_kernel('python3') if PY3 else self.km.start_kernel('python2')

        self.log.debug('>>>>>>  start ipython kernel: %s' % self.kernelid)

        kn = self.km.get_kernel(self.kernelid)
        self.kc = kn.client()
        self.kc.start_channels()
        self.kc.wait_for_ready()
        self.notebook_path = self.get_notebook_path(self.kc)
        self.log_path = self.notebook_path + '/.log'
        if not os.path.exists(self.notebook_path + '/' + IPYTHON_DEFAULT_PATTERN_FILE):
            with open(self.notebook_path + '/' + IPYTHON_DEFAULT_PATTERN_FILE, 'w') as file:
                file.write(IPYTHON_DEFAULT_PATTERN)

        self.log.debug('>>>>> kernel id: ' + self.kernelid)
        self.log.debug(self.notebook_path)

    def write_log_file(self, path, file_full_path=None, msg=None):
        self.log.debug('>>>>> write_log_file')
        if file_full_path is None:
            now = self.get_timestamp()
            path = path + '/' + now.strftime("%Y%m%d")
            if not os.path.exists(path):
                os.makedirs(path)
            file_name = now.strftime("%Y%m%d-%H%M%S") + "-%04d" % (now.microsecond // 1000)
            file_full_path = '{}/{}.log'.format(path, file_name)

        if self.log_file_object is None:
            self.log_file_object = self.open_log_file(file_full_path)

        self.log.debug(file_full_path)
        self.log.debug(self.log_file_object)

        if not msg is None:
            self.log_file_object.write(msg.encode('utf-8'))
        return file_full_path

    def open_log_file(self, path):
        self.log.debug('>>>>> open_log_file')
        return open(path, "a")

    def close_log_file(self):
        self.log.debug('>>>>> close_log_file')
        if self.log_file_object is None:
            self.log.debug('>>>>> close_log_file: not executed because self.log_file_object is None')
            return
        if not self.log_file_object.closed:
            self.log.debug('>>>>> log file closed')
            self.log_file_object.close()
        else:
            self.log.debug('>>>>> close_log_file: not executed because self.log_file_object is already closed')

        self.log.debug('close_log_file: self.log_file_object = None')
        self.log_file_object = None

    def is_log_file_alive(self):
        if not self.log_file_object is None:
            return True
        else:
            return False

    def init_file_property(self):
        self.file_size = 0
        self.file_lines = 0

    def update_file_property(self, closed=False):
        if not closed:
            self.file_size = self.log_file_object.tell()
            # self.file_lines = sum(1 for line in self.log_file_object)
        else:
            self.file_size = os.path.getsize(self.file_full_path)
            self.file_lines = sum(1 for line in open(self.file_full_path))

    def send_code_to_ipython_kernel(self, client=None, code=None):
        if client is None:
            return
        if code is None:
            return
        text = ''
        msg_idle = False
        msg_execute_reply = False
        msg_id = client.execute(code)
        while True:
            try:
                msg = self.kc.get_iopub_msg(block=False, timeout=None)
                # self.log.debug('\n>>>{} iopub msg is'.format(code))
                # self.log.debug(msg)
            except Empty:
                try:
                    msg = self.kc.get_shell_msg(block=False, timeout=None)
                    # self.log.debug('\n>>>{} shell msg is'.format(code))
                    # self.log.debug(msg)
                except Empty:
                    continue
            except Exception as e:
                self.log.debug(e)
                break

            if msg['parent_header'].get('msg_id') != msg_id:
                continue

            msg_type = msg['msg_type']
            content = msg['content']
            if msg_type == 'status' or msg_type == 'execute_reply':
                if msg_type == 'status':
                    if content['execution_state'] == 'idle':
                        msg_idle = True
                    else:
                        continue
                else:
                    msg_execute_reply = True

                if msg_idle and msg_execute_reply:
                    break
                else:
                    continue
            elif msg_type == 'stream':
                try:
                    if 'ExecutionResult' in content['text']:
                        pass
                    else:
                        if content['name'] == 'stdout':
                            text = content['text']
                except Exception as e:
                    self.log.debug(e)
            elif msg_type == 'execute_result':
                text = content['data'].get('text/plain', '')
        return text

    def get_notebook_path(self, client=None):
        # text = self.send_code_to_ipython_kernel(client, '!pwd')
        text = os.getcwd()
        # print('pwd: '+str(text))
        # self.log.debug('current dir: ' + str(text))
        return text.rstrip()

    def get_env_request(self, client=None):
        text1 = self.send_code_to_ipython_kernel(client, '%env')
        # text = text1.replace('\n', '').replace('\r', '').replace('\'', '\"').replace('\"\"', '\"')
        text = text1.replace('\n', '').replace('\r', '').replace('\'', '\"')
        self.log.debug('>>>>>>>>> get_env_request:')
        self.log.debug(text)
        return json.loads(text)

    def get_timestamp(self):
        now = datetime.utcnow() + timedelta(hours=9)
        return now

    def send_clear_content_msg(self):
        clear_content = {'wait': True}
        self.session.send(self.iopub_socket, 'clear_output', clear_content, self._parent_header,
            ident=None, buffers=None, track=False, header=None, metadata=None)

    def kernel_info_request(self, stream, ident, parent):
        # self.log.debug('>>>>>>>> kernel info req')
        # if self.km_working:
        #     self.send_kernel_info = True
        super(PythonKernelBuffered, self).kernel_info_request(stream, ident, parent)

    def get_env(self, client=None):
        try:
            dictionary = self.get_env_request(client)
        except Exception:
            self.log.debug(">>> except get_env ")
            pass

        try:
            env = dictionary[SUMMARIZE_KEY]
            self.log.debug(">>>> lc_wrapper: " + env)
        except Exception:
            env = '1:1:1:1'
            self.log.debug(">>>> cannnot get lc_wrapper: " + env)
        finally:
            env_list = env.split(':')
            if len(env_list) < 4:
                self.log.debug(" len(env_list) < 4 ")
                self.summarize_start_lines = 1
                self.summarize_header_lines = 1
                self.summarize_header_lines = 1
                self.summarize_footer_lines = 1
            else:
                self.log.debug(" len(env_list) >= 4 ")
                if len(env_list[0]) != 0:
                    self.summarize_start_lines = int(env_list[0])
                if len(env_list[1]) != 0:
                    self.summarize_header_lines = int(env_list[1])
                if len(env_list[2]) != 0:
                    self.summarize_exec_lines = int(env_list[2])
                if len(env_list[3]) != 0:
                    self.summarize_footer_lines = int(env_list[3])

        try:
            cell_log_id = dictionary[ENV_LOG_HISTORY_KEY]
            if len(cell_log_id) > 0:
                cell_log_id = cell_log_id.encode(sys.getfilesystemencoding())
                self.log_history_file_path = self.log_path + '/' + cell_log_id + '/' + cell_log_id + '.json'
                self.log.debug('>>>>> history file path: ' + str(self.log_history_file_path))
        except Exception:
            # self.log_history_file_path = None
            self.log.debug('>>>>> exception history file path: ' + str(self.log_history_file_path))
        finally:
            self.data, self.log_history_text = self.read_log_history_file(self.log_history_file_path)

        self.repatter = []
        try:
            text = dictionary[IGNORE_SUMMARIZE_KEY]
        except:
            text = None
        try:
            if text is None or len(text) == 0:
                self.repatter = []
            elif 'file:' in text:
                file_name = text[text.rfind('find:')+6:].strip()
                if file_name == 'default':
                    file_name = IPYTHON_DEFAULT_PATTERN_FILE
                file_path = self.notebook_path + '/' + file_name
                with open(file_path, 'r') as file:
                    patterns = file.readlines()

                    self.log.debug('patterns :')
                    for patt in patterns:
                        patt = patt.strip()
                        self.log.debug(patt)
                        self.repatter.append(re.compile(patt))
            else:
                self.repatter.append(re.compile(text))
        except Exception as e:
            self.repatter = []
            self.keyword_buff_append(u'error : ' + unicode(e))
            self.log.debug(">>>> lc_wrapper_regex: " + str(e))


    def is_summarize_on(self, code):
        regx = r'^\s*!!'
        m = re.match(regx, code, re.M)
        if m:
            return True, code[m.end():]
        else:
            return False, code

    def buff_init(self):
        self.summarize_log_buff = []
        self.summarize_header_buff = []
        self.summarize_footer_buff = []
        self.keyword_buff = []

    def log_buff_flush(self, text=None):
        self.log.debug('>>>>>> log_buff_flush')
        if len(self.summarize_log_buff) > 0:
            self.file_full_path = self.write_log_file(self.log_path, self.file_full_path, u''.join(self.summarize_log_buff))
            del self.summarize_log_buff[:]

    def log_buff_append(self, text=None):
        if self.block_messages:
            return
        if not text is None:
            if isinstance(text, list):
                self.summarize_log_buff.extend(text)
            else:
                self.summarize_log_buff.append(text)

    def keyword_buff_append(self, text=None):
        if not text is None:
            if isinstance(text, list):
                self.keyword_buff.extend(text)
            else:
                self.keyword_buff.append(text)

    def read_log_history_file(self, path):
        self.log.debug('>>>>> read_log_history_file')
        log_history_text = u''
        try:
            with open(path, 'r') as file:
                data = json.load(file)
        except Exception:
            data = None
        else:
            for log in data:
                start = u'start:{}'.format(log.get('start'))
                end = u'end:{}'.format(log.get('end'))
                path = u'path:{}'.format(log.get('path'))
                log_history_text += u'{}\n{}\n{}\n\n'.format(start, end, path)
        return data, log_history_text

    def write_log_history_file(self, path, dict=None):
        self.log.debug('>>>>> write_log_history_file')
        if path is None:
            self.log.debug('>>>>> write_log_history_file: not executed because path is None')
            return
        log = {'code': self.code,
               'path': self.file_full_path.decode(getfilesystemencoding()),
               'start': self.start_time,
               'end': self.end_time,
               'size': self.file_size,
               'lines': self.file_lines}
        if dict is None:
            dict = []
        dict.append(log)

        pathdir = os.path.dirname(path)
        if not os.path.exists(pathdir):
            os.makedirs(pathdir)
        os.symlink(self.file_full_path, os.path.join(pathdir, os.path.basename(self.file_full_path)))

        with open(path, 'w') as file:
            json.dump(dict, file)
            if not os.path.exists(path):
                os.makedirs(path)
        self.log.debug('>>>>> log history file closed')
        self.log_history_file_path = None

    def close_files(self):
        self.log.debug('>>>>> close_files')
        if hasattr(self, "summarize_on") and self.summarize_on:
            self.block_messages = True

            self.log_buff_flush()
            self.close_log_file()
            self.update_file_property(closed=True)
            self.end_time = '{}(JST)'.format(self.get_timestamp().strftime('%Y-%m-%d %H:%M:%S'))
            #save log file path
            self.write_log_history_file(self.log_history_file_path, self.data)

    def init_summarize(self):
        self.block_messages = False
        self.buff_init()
        self.summarize_start_lines = 1
        self.summarize_header_lines = 1
        self.summarize_exec_lines = 1
        self.summarize_footer_lines = 1
        self.count = 0
        self.file_full_path = None
        self.start_time = '{}(JST)'.format(self.get_timestamp().strftime('%Y-%m-%d %H:%M:%S'))
        self.end_time = ''
        self.is_error = False
        self.save_msg_type = None
        self.init_file_property()

        self.log.debug('>>>>> init_summarize: self.log_file_object = None')
        self.log_file_object = None

    def output_hook_summarize(self, msg=None):
        self.log.debug('\niopub msg is')
        self.log.debug(msg)
        msg_type = msg['header']['msg_type']
        content = msg['content']
        if msg_type == 'stream':
            if 'ExecutionResult' in content['text']:
                self.send_response(self.iopub_socket, 'stream', content)
            else:
                self.log_buff_append(content['text'])
                if len(self.summarize_log_buff) > 100:
                    self.log_buff_flush()

                content_text_list = content['text'].splitlines(False)    # with LF
                # save the stderr messages
                if content['name'] == 'stderr':
                    self.keyword_buff_append(content_text_list)
                # save the sentences the keyword matched
                elif not self.repatter is None and len(self.repatter) > 0:
                    for text in content_text_list:
                        for one_repatter in self.repatter:
                            matchOB = one_repatter.search(text)
                            if matchOB:
                                self.log.debug('>>>>> matches ' + matchOB.group() + ' in ' + text)
                                self.keyword_buff_append(text)
                                break
                            else:
                                self.log.debug('>>>>> not match ' + ' in ' + text)

                # save the first few lines
                if len(self.summarize_header_buff) < self.summarize_header_lines:
                    self.summarize_header_buff.extend(content_text_list)
                # save the last few lines
                if len(content_text_list) < self.summarize_footer_lines:
                    if len(content_text_list) + len(self.summarize_footer_buff) > self.summarize_footer_lines:
                        del self.summarize_footer_buff[:len(content_text_list)]
                    self.summarize_footer_buff.extend(content_text_list)
                else:
                    del self.summarize_footer_buff[:]
                    self.summarize_footer_buff.extend(content_text_list[-self.summarize_footer_lines:])

                if self.count < self.summarize_start_lines:
                    self.count += len(content_text_list)
                    stream_content = {'name': content['name'], 'text': content['text']}
                else:
                    self.save_msg_type = 'stream'
                    if self.file_full_path is None:
                        self.log_buff_flush()
                    self.update_file_property()

                    self.send_clear_content_msg()

                    stream_text = u'{}'.format(self.log_history_text)
                    stream_text += u'start time: {}\n'.format(self.start_time)
                    file_full_path = self.file_full_path.decode(getfilesystemencoding())
                    stream_text += u'Output Size(byte): {}, Path: {}\n\n'.format(self.file_size, file_full_path)
                    stream_text += u'{}\n'.format('\n'.join(self.summarize_header_buff[:self.summarize_header_lines]))
                    if len(self.keyword_buff) > 0:
                        stream_text += u'...\n'
                        stream_text += u'\033[0;31m{}\033[0m\n'.format(u'\n'.join(self.keyword_buff[:self.summarize_header_lines * 2]))
                    stream_text += u'...\n'
                    stream_text += u'{}'.format('\n'.join(content_text_list[:self.summarize_exec_lines]))

                    stream_content = {'name': 'stdout', 'text': stream_text}
                self.send_response(self.iopub_socket, 'stream', stream_content)
        elif msg_type in ('display_data', 'execute_result'):
            execute_result = {'data': content['data'], 'execution_count': self.execution_count, 'metadata':{}}
            self.send_response(self.iopub_socket, msg_type, execute_result)
        elif msg_type == 'error':
            self.is_error = True
            self.log_buff_append(content['traceback'])
            # self.session.send(self.iopub_socket, 'error', content, self._parent_header)

    def reply_hook_summarize(self, msg_id, timeout=None):
        """Receive and return the reply for a given request"""
        if timeout is not None:
            deadline = monotonic() + timeout
        while True:
            if timeout is not None:
                timeout = max(0, deadline - monotonic())
            try:
                reply = self.kc.get_shell_msg(timeout=timeout)
                self.log.debug('\nshell msg is')
                self.log.debug(reply)
            except Empty:
                raise TimeoutError("Timeout waiting for reply")
            if reply['parent_header'].get('msg_id') != msg_id:
                # not my reply, someone may have forgotten to retrieve theirs
                continue
            else:
                break

        if hasattr(self, "timer"):
            self.timer.cancel()
            self.log.debug('>>>>> close files: timer cancelled')

        content = reply['content']
        content['execution_count'] = self.execution_count

        if content['status'] == 'ok':
            self.is_error = False
        else:
            self.is_error = True
            error_content = content
            error_content['execution_count'] = self.execution_count
            if self.summarize_on:
                self.log_buff_append(content['traceback'])

        if self.save_msg_type == 'stream':
            self.send_clear_content_msg()
            self.close_files()

            stream_text = u'{}'.format(self.log_history_text)
            stream_text += u'start time: {}\n'.format(self.start_time)
            stream_text += u'end time: {}\n'.format(self.end_time)
            file_full_path = self.file_full_path.decode(getfilesystemencoding())
            stream_text += u'Output Size(byte): {}, Lines: {}, Path: {}\n'.format(self.file_size, self.file_lines, file_full_path)
            stream_text += u'{} keyword matched or stderr happened\n\n'.format(len(self.keyword_buff))
            stream_text += u'{}\n'.format('\n'.join(self.summarize_header_buff[:self.summarize_header_lines]))
            if len(self.keyword_buff) > 0:
                stream_text += u'...\n'
                stream_text += u'\033[0;31m{}\033[0m\n'.format(u'\n'.join(self.keyword_buff[:self.summarize_header_lines * 2]))
            stream_text += u'...\n'
            stream_text += u'{}'.format('\n'.join(self.summarize_footer_buff[-self.summarize_footer_lines:]))

            stream_content = {'name': 'stdout', 'text': stream_text}
            self.send_response(self.iopub_socket, 'stream', stream_content)
        if self.is_error:
            self.session.send(self.iopub_socket, 'error', error_content, self._parent_header,
                                ident=None, buffers=None, track=False, header=None, metadata=None)
        return content

    def execute_request(self, stream, ident, parent):
        self.save_parent = parent
        self.log.debug('parent')
        self.log.debug(self.save_parent)

        # First: this function executes
        # Second: get_env executes
        try:
            cell_log_id = parent[u'content'].get(LOG_HISTORY_KEY_LEVEL1).get(LOG_HISTORY_KEY_LEVEL2).get('current')
        except Exception:
            self.log_history_file_path = None
            self.log.debug('>>>>> history file path: ' + str(self.log_history_file_path))
        else:
            if cell_log_id:
                cell_log_id = cell_log_id.encode(getfilesystemencoding())
                self.log_history_file_path = self.log_path + '/' + cell_log_id + '/' + cell_log_id + '.json'
            self.log.debug('>>>>> history file path: ' + str(self.log_history_file_path))
        finally:
            self.data, self.log_history_text = self.read_log_history_file(self.log_history_file_path)
        super(PythonKernelBuffered, self).execute_request(stream, ident, parent)

    def do_execute(self, code, silent, store_history=True, user_expressions=None,
                   allow_stdin=False):
        if not silent:
            self.code = code
            self.summarize_on, new_code = self.is_summarize_on(code)
            if self.summarize_on:
                self.init_summarize()
                self.get_env(self.kc)
                if not self.log_history_file_path is None:
                    log_history_file_path = self.log_history_file_path.decode(getfilesystemencoding())
                    self.log_buff_append(u'{}\n'.format(log_history_file_path))
                self.log_buff_append(u'{}\n\n'.format(code))  # code
                stdin_hook = self._stdin_hook_default
                output_hook = self.output_hook_summarize
                reply_hook = self.reply_hook_summarize
            else:
                stdin_hook = None
                output_hook = self._output_hook_default
                reply_hook = None

            self._allow_stdin = allow_stdin

        return self.execute_interactive(new_code, silent=silent, store_history=store_history,
                 user_expressions=user_expressions, allow_stdin=allow_stdin, stop_on_error=True,
                 timeout=None, output_hook=output_hook, stdin_hook=stdin_hook, reply_hook=reply_hook)

    def do_shutdown(self, restart):
        self.log.debug('>>>>> do_shutdown :%s' % self.kernelid)
        self.close_files()

        if hasattr(self, "km") and hasattr(self, "kernelid"):
            if self.kernelid in self.km.list_kernel_ids():
                self.km.shutdown_kernel(self.kernelid, now=False, restart=restart)

        return {'status': 'ok', 'restart': restart}

    def _recv_reply(self, msg_id, timeout=None):
        kc = self.kc
        """Receive and return the reply for a given request"""
        if timeout is not None:
            deadline = monotonic() + timeout
        while True:
            if timeout is not None:
                timeout = max(0, deadline - monotonic())
            try:
                reply = kc.get_shell_msg(timeout=timeout)
            except Empty:
                raise TimeoutError("Timeout waiting for reply")
            if reply['parent_header'].get('msg_id') != msg_id:
                # not my reply, someone may have forgotten to retrieve theirs
                continue
            content = reply['content']
            content['execution_count'] = self.execution_count
            return content

    def _stdin_hook_default(self, msg):
        kc = self.kc
        """Handle an input request"""
        content = msg['content']
        if content.get('password', False):
            prompt = self.getpass
        elif sys.version_info < (3,):
            prompt = self.raw_input
        else:
            prompt = self.raw_input

        try:
            raw_data = prompt(content["prompt"])
        except EOFError:
            # turn EOFError into EOF character
            raw_data = '\x04'
        except KeyboardInterrupt:
            sys.stdout.write('\n')
            return

        # only send stdin reply if there *was not* another request
        # or execution finished while we were reading.
        if not (kc.stdin_channel.msg_ready() or kc.shell_channel.msg_ready()):
            kc.input(raw_data)

    def _output_hook_default(self, msg):
        msg_type = msg['header']['msg_type']
        content = msg['content']
        if msg_type == 'stream':
            self.send_response(self.iopub_socket, 'stream', content)
        elif msg_type in ('display_data', 'execute_result'):
            execute_result = {'data': content['data'], 'execution_count': self.execution_count, 'metadata':{}}
            self.send_response(self.iopub_socket, msg_type, execute_result)
        elif msg_type == 'error':
            self.session.send(self.iopub_socket, 'error', content, self._parent_header)
        """Default hook for redisplaying plain-text output"""
        # msg_type = msg['header']['msg_type']
        # content = msg['content']
        # if msg_type == 'stream':
        #     stream = getattr(sys, content['name'])
        #     stream.write(content['text'])
        # elif msg_type in ('display_data', 'execute_result'):
        #     sys.stdout.write(content['data'].get('text/plain', ''))
        # elif msg_type == 'error':
        #     print('\n'.join(content['traceback']), file=sys.stderr)

    def _output_hook_kernel(self, session, socket, parent_header, msg):
        """Output hook when running inside an IPython kernel

        adds rich output support.
        """
        msg_type = msg['header']['msg_type']
        if msg_type in ('display_data', 'execute_result', 'error'):
            session.send(socket, msg_type, msg['content'], parent=parent_header)
        else:
            self._output_hook_default(msg)

    """
    Changes
    -------
    set self.kc as kc
    add paramete: reply_hook
    """
    def execute_interactive(self, code, silent=False, store_history=True,
                 user_expressions=None, allow_stdin=None, stop_on_error=True,
                 timeout=None, output_hook=None, stdin_hook=None, reply_hook=None
                ):
        """Execute code in the kernel interactively

        Output will be redisplayed, and stdin prompts will be relayed as well.
        If an IPython kernel is detected, rich output will be displayed.

        You can pass a custom output_hook callable that will be called
        with every IOPub message that is produced instead of the default redisplay.

        Parameters
        ----------
        code : str
            A string of code in the kernel's language.

        silent : bool, optional (default False)
            If set, the kernel will execute the code as quietly possible, and
            will force store_history to be False.

        store_history : bool, optional (default True)
            If set, the kernel will store command history.  This is forced
            to be False if silent is True.

        user_expressions : dict, optional
            A dict mapping names to expressions to be evaluated in the user's
            dict. The expression values are returned as strings formatted using
            :func:`repr`.

        allow_stdin : bool, optional (default self.allow_stdin)
            Flag for whether the kernel can send stdin requests to frontends.

            Some frontends (e.g. the Notebook) do not support stdin requests.
            If raw_input is called from code executed from such a frontend, a
            StdinNotImplementedError will be raised.

        stop_on_error: bool, optional (default True)
            Flag whether to abort the execution queue, if an exception is encountered.

        timeout: float or None (default: None)
            Timeout to use when waiting for a reply

        output_hook: callable(msg)
            Function to be called with output messages.
            If not specified, output will be redisplayed.

        stdin_hook: callable(msg)
            Function to be called with stdin_request messages.
            If not specified, input/getpass will be called.

        Returns
        -------
        reply: dict
            The reply message for this request
        """
        kc = self.kc
        if reply_hook is None:
            reply_hook = self._recv_reply

        if not kc.iopub_channel.is_alive():
            raise RuntimeError("IOPub channel must be running to receive output")
        if allow_stdin is None:
            allow_stdin = self.allow_stdin
        if allow_stdin and not kc.stdin_channel.is_alive():
            raise RuntimeError("stdin channel must be running to allow input")
        msg_id = kc.execute(code,
                            silent=silent,
                            store_history=store_history,
                            user_expressions=user_expressions,
                            allow_stdin=allow_stdin,
                            stop_on_error=stop_on_error,
        )
        if stdin_hook is None:
            stdin_hook = self._stdin_hook_default
        if output_hook is None:
            # detect IPython kernel
            if 'IPython' in sys.modules:
                from IPython import get_ipython
                ip = get_ipython()
                in_kernel = getattr(ip, 'kernel', False)
                if in_kernel:
                    output_hook = partial(
                        self._output_hook_kernel,
                        ip.display_pub.session,
                        ip.display_pub.pub_socket,
                        ip.display_pub.parent_header,
                    )
        if output_hook is None:
            # default: redisplay plain-text outputs
            output_hook = self._output_hook_default

        # set deadline based on timeout
        if timeout is not None:
            deadline = monotonic() + timeout
        else:
            timeout_ms = None

        poller = zmq.Poller()
        iopub_socket = kc.iopub_channel.socket
        poller.register(iopub_socket, zmq.POLLIN)
        if allow_stdin:
            stdin_socket = kc.stdin_channel.socket
            poller.register(stdin_socket, zmq.POLLIN)
        else:
            stdin_socket = None

        # wait for output and redisplay it
        while True:
            try:
                if timeout is not None:
                    timeout = max(0, deadline - monotonic())
                    timeout_ms = 1e3 * timeout

                events = dict(poller.poll(timeout_ms))
                if not events:
                    raise TimeoutError("Timeout waiting for output")

                if stdin_socket in events:
                    req = kc.stdin_channel.get_msg(timeout=0)
                    stdin_hook(req)
                    continue
                if iopub_socket not in events:
                    continue

                msg = kc.iopub_channel.get_msg(timeout=0)
                if msg['parent_header'].get('msg_id') != msg_id:
                    # not from my request
                    continue
                output_hook(msg)

                # stop on idle
                if msg['header']['msg_type'] == 'status' and \
                msg['content']['execution_state'] == 'idle':
                    break
            except KeyboardInterrupt:
                # Ctrl-C shouldn't crash the kernel
                self.log.error("KeyboardInterrupt caught in execute_interactive")
                self.km.interrupt_kernel(self.kernelid)

                # this timer fire when the ipython kernel didnot interrupt within 5.0 sec.
                self.timer = threading.Timer(5.0, self.close_files)
                self.log.debug('>>>>> close files: timer fired')
                self.timer.start()
                continue
            except:
                self.log.error("a exception caught in execute_interactive")
                continue

        # output is done, get the reply
        if timeout is not None:
            timeout = max(0, deadline - monotonic())
        return reply_hook(msg_id, timeout=timeout)

class LCWrapperKernelManager(IOLoopKernelManager):
    """Kernel manager for LC_wrapper kernel"""

    def shutdown_kernel(self, now=False, restart=False):
        # Stop monitoring for restarting while we shutdown.
        self.stop_restarter()

        self.log.debug("Interrupting the wrapper kernel and its subprocesses")
        self.interrupt_kernel()
        time.sleep(5.0)

        if now:
            self._kill_kernel()
        else:
            self.request_shutdown(restart=restart)
            # Don't send any additional kernel kill messages immediately, to give
            # the kernel a chance to properly execute shutdown actions. Wait for at
            # most 1s, checking every 0.1s.
            self.finish_shutdown()

        self.cleanup(connection_file=not restart)

if __name__ == '__main__':
    from ipykernel.kernelapp import IPKernelApp
    IPKernelApp.launch_instance(kernel_class=PythonKernelBuffered)
