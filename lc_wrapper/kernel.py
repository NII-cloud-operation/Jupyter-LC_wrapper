from __future__ import print_function

from functools import partial
try:
    from queue import Empty  # Python 3
except ImportError:
    from Queue import Empty  # Python 2
import sys
import time
import zmq
import io
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
from datetime import datetime
import os
import os.path
from jupyter_client.multikernelmanager import MultiKernelManager
from jupyter_client.ioloop import IOLoopKernelManager
from jupyter_core.paths import jupyter_runtime_dir
import re
import json
import threading
try:
    from os import getcwdu as getcwd  # Python 2
except ImportError:
    from os import getcwd  # Python 3
import pickle
import dateutil
from .log import ExecutionInfo, parse_execution_info_log

MAX_HISTORY_SUMMARIES = 2

SUMMARIZE_KEY = 'lc_wrapper'
ENV_LOG_HISTORY_KEY = 'lc_wrapper_uuid'
IGNORE_SUMMARIZE_KEY = 'lc_wrapper_regex'
FORCE_SUMMARIZE_KEY = 'lc_wrapper_force'

IPYTHON_DEFAULT_PATTERN_FILE = '.lc_wrapper_regex.txt'
IPYTHON_DEFAULT_PATTERN = '''ERROR|error|Error|Panic|panic|Invalid|invalid|Warning|warning|Bad|bad
(Not|not) (Found|found)
(Device)? not ready
out of (Memory|memory)
interrupt(ed)?|abort(ed)?|stop(ped)?
insecure|inaccessible|Forbidden|forbidden|Denied|denied
Unauthorised|unauthorised|Unauthorized|unauthorized
(No|no|Low|low) (.+ )?(Capacity|capacity|Space|space)
has (encountered|stopped)
is not'''


class BufferedKernelBase(Kernel):
    def __init__(self, **kwargs):
        Kernel.__init__(self, **kwargs)
        self.start_ipython_kernel()

    def start_ipython_kernel(self):
        self.km = MultiKernelManager()
        self.km.connection_dir = jupyter_runtime_dir()
        self.kernelid = self._start_kernel(self.km)

        self.log.debug('>>>>>>  start ipython kernel: %s' % self.kernelid)

        kn = self.km.get_kernel(self.kernelid)
        self.kc = kn.client()
        self.kc.start_channels()
        self.kc.wait_for_ready()
        self.notebook_path = self.get_notebook_path(self.kc)
        self.log_path = os.path.join(self.notebook_path, u'.log')
        if not os.path.exists(os.path.join(self.notebook_path, IPYTHON_DEFAULT_PATTERN_FILE)):
            with open(os.path.join(self.notebook_path, IPYTHON_DEFAULT_PATTERN_FILE), 'w') as f:
                f.write(IPYTHON_DEFAULT_PATTERN)
        self.exec_info = None
        self._init_log()

        self.log.debug('>>>>> kernel id: ' + self.kernelid)
        self.log.debug(self.notebook_path)

    def _start_kernel(self, km):
        raise NotImplementedError()

    def _write_log(self, path, msg):
        if self.file_full_path is None:
            now = datetime.now(dateutil.tz.tzlocal())
            path = os.path.join(path, now.strftime("%Y%m%d"))
            if not os.path.exists(path):
                os.makedirs(path)
            file_name = now.strftime("%Y%m%d-%H%M%S") + "-%04d" % (now.microsecond // 1000)
            self.file_full_path = os.path.join(path, file_name + u'.log')
            self.exec_info.log_path = self.file_full_path

        if self.log_file_object is None:
            self.log_file_object = self.open_log_file(self.file_full_path)

        self.log.debug(self.file_full_path)
        self.log.debug(self.log_file_object)

        if not msg is None:
            self.log_file_object.write(msg)
            self.exec_info.file_size = self.log_file_object.tell()

    def open_log_file(self, path):
        self.log.debug('>>>>> open_log_file')
        return io.open(path, "a", encoding='utf-8')

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

    def _init_log(self):
        self.file_full_path = None
        self.log_file_object = None

    def send_code_to_ipython_kernel(self, client, code):
        stream_text = ''
        execute_result = None
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
                            stream_text += content['text']
                except Exception as e:
                    self.log.debug(e)
            elif msg_type == 'execute_result':
                execute_result = content['data'].get('text/plain', '')
        return execute_result if execute_result is not None else stream_text

    def get_notebook_path(self, client=None):
        return getcwd()

    def _get_env_request(self, client):
        raise NotImplementedError()

    def _get_config(self, client):
        env = self._get_env_request(client)
        config_path = os.path.join(self.notebook_path, '.lc_wrapper')
        if not os.path.exists(config_path):
            return env
        line_pattern = re.compile(r'(\S+)=(".*?"|\S+)')
        config = {}
        with io.open(config_path, 'r', encoding='utf-8') as f:
            for l in f.readlines():
                l = l.strip()
                if len(l) == 0 or l.startswith('#'):
                    continue
                m = line_pattern.match(l)
                if m:
                    config[m.group(1)] = m.group(2)
                else:
                    self.log.warning('Unexpected line: {} at {}'.format(l, config_path))
        for k, v in env.items():
            config[k] = v
        return config

    def send_clear_content_msg(self):
        clear_content = {'wait': True}
        self.session.send(self.iopub_socket, 'clear_output', clear_content, self._parent_header,
            ident=None, buffers=None, track=False, header=None, metadata=None)

    def kernel_info_request(self, stream, ident, parent):
        # self.log.debug('>>>>>>>> kernel info req')
        # if self.km_working:
        #     self.send_kernel_info = True
        super(BufferedKernelBase, self).kernel_info_request(stream, ident, parent)

    def _load_env(self, env):
        summarize = env.get(SUMMARIZE_KEY, '')
        self.log.debug("lc_wrapper = " + summarize)
        summarize_pattern = re.compile(r'^([0-9]*):([0-9]*):([0-9]*):([0-9]*)$')
        summarize_params = summarize_pattern.match(summarize)
        if summarize_params is not None and len(summarize_params.group(1)) != 0:
            self.summarize_start_lines = int(summarize_params.group(1))
        if summarize_params is not None and len(summarize_params.group(2)) != 0:
            self.summarize_header_lines = int(summarize_params.group(2))
        if summarize_params is not None and len(summarize_params.group(3)) != 0:
            self.summarize_exec_lines = int(summarize_params.group(3))
        if summarize_params is not None and len(summarize_params.group(4)) != 0:
            self.summarize_footer_lines = int(summarize_params.group(4))
        self.summarize_start_lines = max(self.summarize_start_lines,
                                         self.summarize_header_lines + \
                                         self.summarize_footer_lines + 1)

        cell_log_id = env.get(ENV_LOG_HISTORY_KEY, None)
        if cell_log_id is not None:
            # Overwrite log history file name
            self.log_history_file_path = os.path.join(self.log_path,
                                                      cell_log_id,
                                                      cell_log_id + u'.json')
            self.log_history_id = cell_log_id
        self.log_history_data, self.log_history_text = self._read_log_history_file()

        self.repatter = []
        text = env.get(IGNORE_SUMMARIZE_KEY, 'file:default')
        if text is None or len(text) == 0:
            pass
        elif 'file:' in text:
            file_name = text[text.rfind('find:')+6:].strip()
            if file_name == 'default':
                file_name = IPYTHON_DEFAULT_PATTERN_FILE
            file_path = os.path.join(self.notebook_path, file_name)
            if os.path.exists(file_path):
                with open(file_path, 'r') as file:
                    patterns = file.readlines()

                    self.log.debug('patterns :')
                    for patt in patterns:
                        patt = patt.strip()
                        self.log.debug(patt)
                        try:
                            self.repatter.append(re.compile(patt))
                        except Exception as e:
                            self.keyword_buff_append(u'error : ' + unicode(e))
                            self.log.warning("lc_wrapper_regex: " + str(e))
            else:
                self.keyword_buff_append(u'error : ' + u'Not found {}'.format(file_path))
                self.log.warning('lc_wrapper_regex: ' + u'Not found {}'.format(file_path))
        else:
            try:
                self.repatter.append(re.compile(text))
            except Exception as e:
                self.keyword_buff_append(u'error : ' + unicode(e))
                self.log.warning("lc_wrapper_regex: " + str(e))

    def is_summarize_on(self, code, env):
        force = None
        if FORCE_SUMMARIZE_KEY in env:
            force_text = env[FORCE_SUMMARIZE_KEY].strip().lower()
            if force_text == 'on':
                force = True
            elif force_text == 'off':
                force = False
        regx = r'^\s*!!'
        m = re.match(regx, code, re.M)
        if m:
            return (force if force is not None else True,
                    code[m.end():])
        else:
            return (force if force is not None else False,
                    code)

    def buff_init(self):
        self.summarize_log_buff = []
        self.summarize_header_buff = []
        self.summarize_last_buff = []
        self.keyword_buff = []

    def _log_buff_flush(self, force=False):
        if force or self.file_full_path is None or \
           len(self.summarize_log_buff) > 100:
            self._write_log(self.log_path, u''.join(self.summarize_log_buff))
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

    def _read_log_history_file(self):
        if self.log_history_file_path is not None and \
           os.path.exists(self.log_history_file_path):
            with open(self.log_history_file_path, 'r') as f:
                data = json.load(f)
            log_history_text = u''
            for log in data[-MAX_HISTORY_SUMMARIES:]:
                log_history_text += parse_execution_info_log(log).to_stream() + u'\n'
            return data, log_history_text
        else:
            return [], u''

    def _write_log_history_file(self, data):
        if self.log_history_file_path is None:
            self.log.debug('Skipped to save log history')
            return
        data.append(self.exec_info.to_log())

        pathdir = os.path.dirname(self.log_history_file_path)
        if not os.path.exists(pathdir):
            os.makedirs(pathdir)
        log_full_dir, log_filename = os.path.split(self.file_full_path)
        log_full_dir, log_dirname = os.path.split(log_full_dir)
        os.symlink(os.path.join('..', log_dirname, log_filename),
                   os.path.join(pathdir, os.path.basename(self.file_full_path)))
        with open(self.log_history_file_path, 'w') as f:
            json.dump(data, f)
        self.log.debug('Log history saved: {}'.format(self.log_history_file_path))
        self.log_history_file_path = None

    def close_files(self):
        self.log.debug('>>>>> close_files')
        if hasattr(self, "summarize_on") and self.summarize_on:
            self.exec_info.finished(len(self.keyword_buff))
            self.log_buff_append(u'\n----\n{}----\n'.format(self.exec_info.to_stream_footer()))
            for result in self.result_files:
                self.log_buff_append(u'result: {}\n'.format(result))
            self.block_messages = True

            self._log_buff_flush(force=True)
            self.close_log_file()
            #save log file path
            self._write_log_history_file(self.log_history_data)

    def init_summarize(self):
        self.block_messages = False
        self.buff_init()
        self.summarize_start_lines = 50
        self.summarize_header_lines = 20
        self.summarize_exec_lines = 1
        self.summarize_footer_lines = 20
        self.count = 0
        self.result_files = []
        self._init_log()

    def _store_result(self, result):
        if self.file_full_path is None:
            self.log.error('Log file already closed. Skip to store results')
            return
        log_dir, log_name = os.path.split(self.file_full_path)
        log_name_body, _ = os.path.splitext(log_name)
        result_file = os.path.join(log_dir,
                                   u'{}-{}.pkl'.format(log_name_body,
                                                       len(self.result_files)))
        with open(result_file, 'wb') as f:
            pickle.dump(result, f)
        self.result_files.append(result_file)

    def _store_last_lines(self, content_text_list):
        # save the last few lines
        lines = max(self.summarize_footer_lines, self.summarize_start_lines)
        if len(content_text_list) < lines:
            if len(content_text_list) + len(self.summarize_last_buff) > lines:
                del self.summarize_last_buff[:len(content_text_list)]
            self.summarize_last_buff.extend(content_text_list)
        else:
            del self.summarize_last_buff[:]
            self.summarize_last_buff.extend(content_text_list[-lines:])

    def _output_hook_summarize(self, msg=None):
        self.log.debug('\niopub msg is')
        self.log.debug(msg)
        msg_type = msg['header']['msg_type']
        content = msg['content']
        if msg_type == 'stream':
            if 'ExecutionResult' in content['text']:
                self.send_response(self.iopub_socket, 'stream', content)
            else:
                self.log_buff_append(content['text'])
                self._log_buff_flush()

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
                self._store_last_lines(content_text_list)

                if self.count < self.summarize_start_lines:
                    self.count += len(content_text_list)
                    stream_content = {'name': content['name'], 'text': content['text']}
                else:
                    self._log_buff_flush()

                    self.send_clear_content_msg()

                    stream_text = u'{}'.format(self.log_history_text)
                    stream_text += self.exec_info.to_stream() + u'----\n'

                    stream_text += u'{}\n'.format('\n'.join(self.summarize_header_buff[:self.summarize_header_lines]))
                    if len(self.keyword_buff) > 0:
                        stream_text += u'...\n'
                        stream_text += u'\033[0;31m{}\033[0m\n'.format(u'\n'.join(self.keyword_buff[:self.summarize_header_lines * 2]))
                    stream_text += u'...\n'
                    stream_text += u'{}'.format('\n'.join(content_text_list[:self.summarize_exec_lines]))

                    stream_content = {'name': 'stdout', 'text': stream_text}
                self.send_response(self.iopub_socket, 'stream', stream_content)
        elif msg_type in ('display_data', 'execute_result'):
            execute_result = content.copy()
            execute_result['execution_count'] = self.execution_count
            self._store_result({'msg_type': msg_type, 'content': execute_result})
            self.send_response(self.iopub_socket, msg_type, execute_result)
        elif msg_type == 'error':
            error_result = content.copy()
            error_result['execution_count'] = self.execution_count
            self._store_result({'msg_type': msg_type, 'content': error_result})
            self.send_response(self.iopub_socket, msg_type, error_result)

    def _reply_hook_summarize(self, msg_id, timeout=None):
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

        self.close_files()
        self.send_clear_content_msg()

        stream_text = u'{}'.format(self.log_history_text)
        stream_text += self.exec_info.to_stream() + u'----\n'

        if self.count < self.summarize_start_lines:
            stream_text += u'\n'.join(self.summarize_last_buff)
        else:
            stream_text += u'{}\n'.format('\n'.join(self.summarize_header_buff[:self.summarize_header_lines]))
            if len(self.keyword_buff) > 0:
                stream_text += u'...\n'
                stream_text += u'\033[0;31m{}\033[0m\n'.format(u'\n'.join(self.keyword_buff[:self.summarize_header_lines * 2]))
            stream_text += u'...\n'
            stream_text += u'{}'.format('\n'.join(self.summarize_last_buff[-self.summarize_footer_lines:]))

        stream_content = {'name': 'stdout', 'text': stream_text}
        self.send_response(self.iopub_socket, 'stream', stream_content)

        # Send exeuction result again because last result can be cleared
        for resultf in self.result_files:
            with open(resultf, 'rb') as f:
                result = pickle.load(f)
                self.session.send(self.iopub_socket,
                                  result['msg_type'],
                                  result['content'],
                                  self._parent_header,
                                  ident=None,
                                  buffers=None,
                                  track=False,
                                  header=None,
                                  metadata=None)
        self.result_files = []
        return content

    def _get_cell_id(self, parent):
        if 'content' not in parent:
            return None
        content = parent['content']
        if 'lc_cell_data' not in content:
            return None
        lc_cell_data = content['lc_cell_data']
        if 'lc_cell_meme' not in lc_cell_data:
            return None
        lc_cell_meme = lc_cell_data['lc_cell_meme']
        if 'current' not in lc_cell_meme:
            return None
        return lc_cell_meme['current']

    def execute_request(self, stream, ident, parent):
        cell_log_id = self._get_cell_id(parent)
        if cell_log_id is not None:
            self.log_history_file_path = os.path.join(self.log_path,
                                                      cell_log_id,
                                                      cell_log_id + u'.json')
        else:
            self.log_history_file_path = None
        self.log_history_id = cell_log_id
        self.log_history_data, self.log_history_text = self._read_log_history_file()
        super(BufferedKernelBase, self).execute_request(stream, ident, parent)

    def do_execute(self, code, silent, store_history=True, user_expressions=None,
                   allow_stdin=False):
        self.exec_info = ExecutionInfo(code)
        if not silent:
            env = self._get_config(self.kc)
            self.summarize_on, new_code = self.is_summarize_on(code, env)
            if self.summarize_on:
                self.init_summarize()
                self._load_env(env)
                if not self.log_history_id is None:
                    meme = {'lc_cell_meme': {'current': self.log_history_id}}
                    self.log_buff_append(u'{}\n----\n'.format(json.dumps(meme)))
                self.log_buff_append(u'{}\n----\n'.format(code))  # code
                self._log_buff_flush()
                self.log_buff_append(self.exec_info.to_stream_header() + u'----\n')
                stdin_hook = self._stdin_hook_default
                output_hook = self._output_hook_summarize
                reply_hook = self._reply_hook_summarize
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
                self.log.info("KeyboardInterrupt caught in execute_interactive")
                self.km.interrupt_kernel(self.kernelid)

                # this timer fire when the ipython kernel didnot interrupt within 5.0 sec.
                self.timer = threading.Timer(5.0, self.close_files)
                self.log.debug('>>>>> close files: timer fired')
                self.timer.start()
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
