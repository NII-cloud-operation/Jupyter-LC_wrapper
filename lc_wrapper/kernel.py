from __future__ import print_function

try:
    from queue import Empty  # Python 3
except ImportError:
    from Queue import Empty  # Python 2
import time
import io

from ipykernel.kernelbase import Kernel
from datetime import datetime
import os
import os.path
from jupyter_client.manager import KernelManager
from jupyter_client.ioloop import IOLoopKernelManager
from jupyter_core.application import JupyterApp
import re
import json
from threading import (Thread, Event, Timer)

try:
    from os import getcwdu as getcwd  # Python 2
except ImportError:
    from os import getcwd  # Python 3
import pickle
import dateutil
from .log import ExecutionInfo

from traitlets.config.configurable import LoggingConfigurable, MultipleInstanceError
from traitlets import (
    Unicode, default
)
from ipython_genutils import py3compat
from ipython_genutils.py3compat import PY3
from types import MethodType
from fluent import sender

SUMMARIZE_KEY = 'lc_wrapper'
ENV_LOG_HISTORY_KEY = 'lc_wrapper_uuid'
IGNORE_SUMMARIZE_KEY = 'lc_wrapper_regex'
FORCE_SUMMARIZE_KEY = 'lc_wrapper_force'

IPYTHON_DEFAULT_PATTERN_FILE = '.lc_wrapper_regex.txt'
IPYTHON_DEFAULT_PATTERN = '''ERROR|error|Error|Panic|panic|Invalid|invalid|Warning|warning|Bad|bad
FAIL|Fail|fail
(Not|not) (Found|found)
(Device)? not ready
out of (Memory|memory)
interrupt(ed)?|abort(ed)?|stop(ped)?
insecure|inaccessible|Forbidden|forbidden|Denied|denied
Unauthorised|unauthorised|Unauthorized|unauthorized
(No|no|Low|low) (.+ )?(Capacity|capacity|Space|space)
has (encountered|stopped)
is not
initialize(d)?|initialise(d)?|start(ed)?|restart(ed)?|spawn(ed)?|complete(d)?
finish(ed)?|resume(d)?|begin|attach(ed)?|detach(ed)?|reboot(ed)?|suspend(ed)?
done|terminate(d)?|open(ed)?|close(d)?|(dis)?connect(ed)?|establish(ed)?
allocate(d)?|assign(ed)?|load(ed)?|(in|re)?activate(d)?|block(ed)?|kill(ed)?
refuse(d)?|insufficient|lack
link(ed)? (up|down)'''


class ChannelReaderThread(Thread, LoggingConfigurable):

    _exiting = False

    def __init__(self, kernel, client, stream, session, channel, **kwargs):
        Thread.__init__(self, **kwargs)
        LoggingConfigurable.__init__(self, **kwargs)

        self.daemon = True
        self.channel_name = channel
        self.channel = getattr(client, channel + "_channel")
        self.kernel = kernel
        self.client = client
        self.stream = stream
        self.session = session

        self.log.debug("init ChannelReaderThread: channel_name=%s",
                       self.channel_name)

    def run(self):
        self.log.debug("start ChannelReaderThread: channel_name=%s",
                       self.channel_name)

        while True:
            try:
                msg = self.channel.get_msg(block=True, timeout=0.2)
                self.log.debug("Received %s message: %s",
                               self.channel_name, str(msg))

                msg_type = msg['msg_type']
                idle = False
                status_msg = False

                if self.channel_name == 'iopub':
                    content = msg['content']
                    if msg_type == 'status':
                        status_msg = True
                        if content['execution_state'] == 'idle':
                            self.kernel.idle_parent_header = msg['parent_header']
                            self.kernel.idle_event.set()
                            idle = True

                if self.kernel.no_forwarding:
                    self.kernel.msg_buffer.append(msg)
                    continue

                if msg['parent_header']['msg_type'] == 'shutdown_request':
                    continue

                msg_id = msg['parent_header']['msg_id']
                parent_header = self.kernel.parent_headers.get(msg_id)
                self.log.debug("parent_header: %s", str(parent_header))

                if self.channel_name == 'iopub':
                    ident = self.kernel._topic(msg_type)
                    msg_content = self.kernel._hook_iopub_msg(parent_header, msg)
                else:
                    ident = self.kernel._parent_ident
                    msg_content = msg['content']

                if not status_msg:
                    self.session.send(self.stream,
                                      msg_type,
                                      msg_content,
                                      parent=parent_header,
                                      ident=ident,
                                      header=msg['header'],
                                      metadata=msg['metadata'],
                                      buffers=msg['buffers'])

                if self.channel_name == 'stdin' and msg_type == 'input_request':
                    self.log.debug("do input_request")
                    self.input_request()

                if idle:
                    parent_msg_id = msg['parent_header'].get('msg_id')
                    if parent_msg_id is not None:
                        self.kernel._remove_parent_header(parent_msg_id)
                    if not self.kernel.flush_stream_event.is_set():
                        self.kernel._send_last_stdout_stream_text()
                        self.kernel.flush_stream_event.set()
            except Empty as e:
                pass
            except Exception as e:
                self.log.error(e, exc_info=True)
            finally:
                if self._exiting:
                    break

        self.log.debug("exit ChannelReaderThread: %s", self.channel_name)

    def input_request(self):
        self.log.debug("wait input_reply")
        while True:
            try:
                ident, reply = self.session.recv(self.stream, 0)
            except Exception:
                self.log.warn("Invalid Message:", exc_info=True)
            except KeyboardInterrupt:
                # re-raise KeyboardInterrupt, to truncate traceback
                raise KeyboardInterrupt
            else:
                break

        self.log.debug("input_reply: %s", str(reply))
        msg = self.client.session.msg(reply['msg_type'],
                                      content=reply['content'],
                                      parent=reply['parent_header'],
                                      header=reply['header'],
                                      metadata=reply['metadata'])
        self.client.stdin_channel.send(msg)

    def stop(self):
        if self.isAlive():
            self._exiting = True
            self.join()


class BufferedKernelBase(Kernel):

    blocking_msg_types = [
        'execute_request',
        'history_request',
        'complete_request',
        'inspect_request',
        'kernel_info_request',
        'comm_info_request',
        'shutdown_request'
    ]
    proxy_channles = ['iopub', 'stdin']

    threads = {}

    parent_headers = {}
    no_forwarding = False
    msg_buffer = []
    idle_event = Event()
    idle_parent_header = None
    flush_stream_event = Event()

    execute_request_msg_id = None

    data_dir = Unicode()
    @default('data_dir')
    def _data_dir_default(self):
        app = None
        try:
            if JupyterApp.initialized():
                app = JupyterApp.instance()
        except MultipleInstanceError:
            pass
        if app is None:
            # create an app, without the global instance
            app = JupyterApp()
            app.initialize(argv=[])
        return app.data_dir

    server_signature_file = Unicode(
        help="""The file where the server signature is stored."""
    ).tag(config=True)
    @default('server_signature_file')
    def _server_signature_file_default(self):
        if 'lc_nblineage_server_signature_path' in os.environ:
            return os.environ['lc_nblineage_server_signature_path']
        if not self.data_dir:
            return ''
        return os.path.join(self.data_dir, 'server_signature')

    def __init__(self, **kwargs):
        Kernel.__init__(self, **kwargs)

        if 'lc_wrapper_fluentd_host' in os.environ:
            fluentd_host = os.environ['lc_wrapper_fluentd_host']
            fluentd_port = int(os.environ.get('lc_wrapper_fluentd_port', '24224'))
            fluentd_tag = os.environ.get('lc_wrapper_fluentd_tag', 'lc_wrapper')
            self.sender = sender.FluentSender(fluentd_tag,
                                              host=fluentd_host,
                                              port=fluentd_port)
            self.log.info('lc_wrapper: Enabled fluent logger: host=%s, port=%s, tag=%s',
                          fluentd_host, fluentd_port, fluentd_tag)
        else:
            self.sender = None

        self._init_message_handler()
        self.start_ipython_kernel()

    def _init_message_handler(self):

        def handler(self, stream, ident, parent):
            self.log.debug("Received shell message: %s", str(parent))

            msg_type = parent['msg_type']
            content = parent['content']

            self._hook_request_msg(parent)

            self.idle_event.clear()

            msg = self.kc.session.msg(msg_type, content)
            msgid = msg['header']['msg_id']
            self.log.debug("save parent_header: %s => %s", msgid, str(parent['header']))
            self.parent_headers[msgid] = parent['header']

            self.kc.shell_channel.send(msg)

            reply_msg = None
            if msg_type in self.blocking_msg_types:
                while True:
                    try:
                        reply_msg = self.kc._recv_reply(msgid, timeout=None)
                        break
                    except KeyboardInterrupt:
                        self.log.debug("KeyboardInterrupt", exc_info=True)
                        # propagate SIGINT to wrapped kernel
                        self.km.interrupt_kernel()

                        # this timer fire when the ipython kernel didnot interrupt within 5.0 sec.
                        self.timer = Timer(5.0, self.close_files)
                        self.log.debug('>>>>> close files: timer fired')
                        self.timer.start()

                reply_msg_content = self._hook_reply_msg(reply_msg)

                self.log.debug('reply: %s', reply_msg)
                reply_msg = self.session.send(stream,
                                              reply_msg['msg_type'],
                                              reply_msg_content,
                                              parent, ident,
                                              header=reply_msg['header'],
                                              metadata=reply_msg['metadata'],
                                              buffers=reply_msg['buffers'])

                self._post_send_reply_msg(parent, reply_msg)

            self._wait_for_idle(msgid)
            self._post_wait_for_idle(parent, reply_msg)

        for msg_type in self.msg_types:
            if msg_type == 'kernel_info_request':
                continue
            if msg_type == 'shutdown_request':
                continue

            self.log.debug('override shell message handler: msg_type=%s', msg_type)

            if PY3:
                setattr(self, msg_type, MethodType(handler, self))
            else:
                setattr(self, msg_type, MethodType(handler, self, type(self)))
            self.shell_handlers[msg_type] = getattr(self, msg_type)

        comm_msg_types = ['comm_open', 'comm_msg', 'comm_close']
        for msg_type in comm_msg_types:
            self.log.debug('init shell comm message handler: msg_type=%s', msg_type)

            if PY3:
                setattr(self, msg_type, MethodType(handler, self))
            else:
                setattr(self, msg_type, MethodType(handler, self, type(self)))
            self.shell_handlers[msg_type] = getattr(self, msg_type)

    def start_ipython_kernel(self):
        kernel_name = self._get_wrapped_kernel_name()
        self.km = KernelManager(kernel_name=kernel_name,
                                client_class='jupyter_client.blocking.BlockingKernelClient')
        self.log.debug('kernel_manager: %s', str(self.km))

        self.log.info('start wrapped kernel: %s', kernel_name)
        self.km.start_kernel()
        self.kc = self.km.client()
        self.log.debug('kernel_client: %s', str(self.kc))

        self.log.debug('start_channels')
        self.kc.start_channels()

        self.flush_stream_event.set()

        try:
            self.log.debug('wait for ready of wrapped kernel')
            self.kc.wait_for_ready(timeout=None)
        except RuntimeError:
            self.kc.stop_channels()
            self.km.shutdown_kernel()
            raise

        for channel in self.proxy_channles:
            stream = getattr(self, channel + '_socket')
            thread = ChannelReaderThread(self, self.kc, stream, self.session, channel)
            thread.start()
            self.threads[channel] = thread

        self.notebook_path = self.get_notebook_path(self.kc)
        self.log_path = os.path.join(self.notebook_path, u'.log')
        if not os.path.exists(os.path.join(self.notebook_path, IPYTHON_DEFAULT_PATTERN_FILE)):
            with open(os.path.join(self.notebook_path, IPYTHON_DEFAULT_PATTERN_FILE), 'w') as f:
                f.write(IPYTHON_DEFAULT_PATTERN)
        self.exec_info = None

        self.log.debug('notebook_path: %s', self.notebook_path)

    def _get_wrapped_kernel_name(self, km):
        raise NotImplementedError()

    def _remove_parent_header(self, msg_id):
        if msg_id in self.parent_headers:
            parent_header = self.parent_headers[msg_id]
            self.log.debug("remove parent_header: %s => %s", msg_id, str(parent_header))
            del self.parent_headers[msg_id]

    def _hook_request_msg(self, parent):
        msg_type = parent['msg_type']
        if msg_type == 'execute_request':
            self._hook_execute_request_msg(parent)

    def _hook_execute_request_msg(self, parent):
        try:
            content = parent[u'content']
            code = py3compat.cast_unicode_py2(content[u'code'])
            silent = content[u'silent']
            allow_stdin = content.get('allow_stdin', False)
        except:
            self.log.error("Got bad msg: ")
            self.log.error("%s", parent)
            return

        self.execute_request_msg_id = parent['header']['msg_id']

        if not silent:
            self.execution_count += 1

        cell_log_id = self._get_cell_id(parent)
        if cell_log_id is not None:
            self.log_history_file_path = os.path.join(self.log_path,
                                                      cell_log_id,
                                                      cell_log_id + u'.json')
        else:
            self.log_history_file_path = None
        self.log_history_id = cell_log_id
        self.log_history_data = self._read_log_history_file()

        notebook_data = self._get_notebook_data(parent)

        self.exec_info = ExecutionInfo(code, self.get_server_signature(), notebook_data)
        if not silent:
            env = self._get_config(self.kc)
            self.summarize_on, new_code = self.is_summarize_on(code, env)
            self._init_default_config()
            self._start_log()
            if self.summarize_on:
                self._start_summarize()
            self._load_env(env)
            if not self.log_history_id is None:
                meme = {'lc_cell_meme': {'current': self.log_history_id}}
                self.log_buff_append(u'{}\n----\n'.format(json.dumps(meme)))
            self.log_buff_append(u'{}\n----\n'.format(code))  # code
            self._log_buff_flush()
            self.log_buff_append(self.exec_info.to_logfile_header() + u'----\n')
            content[u'code'] = new_code

            self.flush_stream_event.clear()

            self._allow_stdin = allow_stdin

    def _hook_reply_msg(self, reply_msg):
        if reply_msg['msg_type'] == 'execute_reply':
            return self._hook_execute_reply_msg(reply_msg)
        return reply_msg['content']

    def _hook_execute_reply_msg(self, reply):
        if hasattr(self, "timer"):
            self.timer.cancel()
            self.log.debug('>>>>> close files: timer cancelled')

        content = reply['content']
        content['execution_count'] = self.execution_count

        return content

    def _post_send_reply_msg(self, parent, reply_msg):
        msg_type = parent['msg_type']
        if msg_type == 'execute_request':
            content = parent['content']
            silent = content['silent']
            stop_on_error = content.get('stop_on_error', True)
            if not silent and reply_msg['content']['status'] == u'error' and stop_on_error:
                self._abort_queues()

    def _post_wait_for_idle(self, parent, reply_msg):
        if reply_msg is None:
            return
        if reply_msg['msg_type'] == 'execute_reply':
            self.log.debug('waiting for flushing stdout stream')
            self.flush_stream_event.wait()
            self.log.debug('flushed stdout stream')

            self.execute_request_msg_id = None

    def _hook_iopub_msg(self, parent_header, msg):
        msg_id = parent_header['msg_id']

        content = msg['content']
        # replace msg_id in the content
        self._replace_msg_id(msg_id, msg['parent_header']['msg_id'], content)

        if self.execute_request_msg_id == msg_id:
            return self._output_hook(msg)

        return content

    def _replace_msg_id(self, msg_id, wrapped_msg_id, content):
        for k, v in content.items():
            if isinstance(v, dict):
                self._replace_msg_id(msg_id, wrapped_msg_id, v)
            elif v == wrapped_msg_id:
                content[k] = msg_id
                self.log.debug('replace msg_id in content: %s => %s',
                               wrapped_msg_id, msg_id)

    def _write_log(self, msg):
        if not msg is None:
            self.log_file_object.write(msg)
            self.exec_info.file_size = self.log_file_object.tell()

    def open_log_file(self, path):
        self.log.debug('>>>>> open_log_file')

        if self.log_file_object is not None:
            return

        now = datetime.now(dateutil.tz.tzlocal())
        path = os.path.join(path, now.strftime("%Y%m%d"))
        if not os.path.exists(path):
            os.makedirs(path)
        file_name = now.strftime("%Y%m%d-%H%M%S") + "-%04d" % (now.microsecond // 1000)
        self.file_full_path = os.path.join(path, file_name + u'.log')
        self.exec_info.log_path = self.file_full_path

        self.log_file_object = io.open(self.file_full_path, "a", encoding='utf-8')

        self.log.debug(self.file_full_path)
        self.log.debug(self.log_file_object)

    def close_log_file(self):
        self.log.debug('>>>>> close_log_file')
        if self.log_file_object is None:
            self.log.debug('>>>>> close_log_file: not executed because self.log_file_object is None')
            return
        if not self.log_file_object.closed:
            self.log.debug('>>>>> log file closed')
            self.log_file_object.close()
            self.send_fluent_log()
        else:
            self.log.debug('>>>>> close_log_file: not executed because self.log_file_object is already closed')

        self.log.debug('close_log_file: self.log_file_object = None')
        self.log_file_object = None

    def send_fluent_log(self):
        if self.sender is None:
            return
        self.log.debug('>>>>> send_fluent_log')

        record = {}
        with io.open(self.exec_info.log_path, 'r') as f:
            record['log'] = f.read()
        self.sender.emit(None, record)

        self.log.info('lc_wrapper: send_fluent_log: cell_meme=%s, uid=%s, gid=%s',
                      self.log_history_id, os.getuid(), os.getgid(), self.get_server_signature())

    def get_server_signature(self):
        if os.path.exists(self.server_signature_file):
            with io.open(self.server_signature_file, 'r') as f:
                return f.read()
        else:
            return None

    def send_code_to_ipython_kernel(self, client, code):
        self.msg_buffer = []

        self.idle_event.clear()
        self.no_forwarding = True

        msg_id = client.execute(code)

        self.kc._recv_reply(msg_id, timeout=None)
        self._wait_for_idle(msg_id)
        self.no_forwarding = False

        msgs = [m for m in self.msg_buffer
                if m['parent_header'].get('msg_id') == msg_id]
        self.msg_buffer = []

        stream_msgs = [m for m in msgs
                       if m['msg_type'] == 'stream' and m['content']['name'] == 'stdout']
        stream_text = ''.join([m['content']['text'] for m in stream_msgs])

        execute_results = [m for m in msgs
                           if m['msg_type'] == 'execute_result']
        if len(execute_results) > 0:
            content = execute_results[-1]['content']
            execute_result = content['data'].get('text/plain', '')
        else:
            execute_result = None

        return execute_result if execute_result is not None else stream_text

    def _wait_for_idle(self, msg_id):
        self.log.debug('waiting for idle: msg_id=%s', msg_id)
        while True:
            self.idle_event.wait()
            if self.idle_parent_header['msg_id'] != msg_id:
                self.log.warn('unexpected idle message received: expected msg_id=%s, received msg_id=%s',
                              msg_id, self.idle_parent_header['msg_id'])
                continue
            self.log.debug('idle: msg_id=%s', msg_id)
            return

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
        self.log_history_data = self._read_log_history_file()

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

    def _log_buff_flush(self, force=False):
        if force or len(self.log_buff) > 100:
            self._write_log(u''.join(self.log_buff))
            del self.log_buff[:]

    def log_buff_append(self, text=None):
        if self.block_messages:
            return
        if not text is None:
            if isinstance(text, list):
                self.log_buff.extend(text)
            else:
                self.log_buff.append(text)

    def keyword_buff_append(self, text, highlight=True):
        if isinstance(text, list):
            self.keyword_buff.extend([u'\033[0;31m{}\033[0m'.format(t)
                                      if highlight else t for t in text])
        else:
            self.keyword_buff.append(u'\033[0;31m{}\033[0m'.format(text)
                                     if highlight else text)

    def display_keyword_buff(self):
        if len(self.keyword_buff) == 0:
            return ''
        stream_text = u'...\n'
        stream_text += u'\n'.join(self.keyword_buff[:self.summarize_header_lines * 2]) + '\n'
        if len(self.keyword_buff) <= self.summarize_header_lines * 2:
            return stream_text
        msg = u'Matched lines exceed maximum number of view ({})' \
              .format(self.summarize_header_lines * 2)
        stream_text += u'\033[0;31m{}\033[0m\n'.format(msg)
        return stream_text

    def highlight_keywords(self, text):
        matched = [p.search(text) for p in self.repatter]
        matched = [m for m in matched if m is not None]
        if len(matched) == 0:
            return None
        remain = text
        result = None
        while len(matched) > 0:
            left = min([m.start() for m in matched])
            if result is None:
                result = remain[:left]
            else:
                result += remain[:left]
            keywords = [m.group() for m in matched if m.start() == left]
            keyword = sorted(keywords, key=lambda s: len(s))[-1]
            result += u'\033[0;31m{}\033[0m'.format(keyword)
            remain = remain[left + len(keyword):]

            matched = [p.search(remain) for p in self.repatter]
            matched = [m for m in matched if m is not None]
        return result + remain

    def _read_log_history_file(self):
        if self.log_history_file_path is not None and \
           os.path.exists(self.log_history_file_path):
            with open(self.log_history_file_path, 'r') as f:
                data = json.load(f)
            return data
        else:
            return []

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
        if self.log_file_object is not None:
            self.exec_info.finished(len(self.keyword_buff))
            self.log_buff_append(u'\n----\n{}----\n'.format(self.exec_info.to_logfile_footer()))
            for result in self.result_files:
                self.log_buff_append(u'result: {}\n'.format(result))
            self.block_messages = True

            self._log_buff_flush(force=True)
            self.close_log_file()
            #save log file path
            self._write_log_history_file(self.log_history_data)

    def _init_default_config(self):
        self.summarize_start_lines = 50
        self.summarize_header_lines = 20
        self.summarize_exec_lines = 1
        self.summarize_footer_lines = 20

    def _start_summarize(self):
        self.count = 0
        self.summarize_header_buff = []
        self.summarize_last_buff = []

    def _start_log(self):
        self.block_messages = False
        self.log_buff = []
        self.keyword_buff = []
        self.result_files = []
        self.file_full_path = None
        self.log_file_object = None

        self.open_log_file(self.log_path)

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

    def _output_hook(self, msg=None):
        msg_type = msg['header']['msg_type']
        content = msg['content']
        if msg_type == 'stream':
            if 'ExecutionResult' in content['text']:
                return content
            else:
                self.log_buff_append(content['text'])
                self._log_buff_flush()

                content = msg['content']
                content_text_list = content['text'].splitlines(False)    # with LF

                # save the stderr messages
                if content['name'] == 'stderr':
                    self.keyword_buff_append(content_text_list)
                # save the sentences the keyword matched
                elif not self.repatter is None and len(self.repatter) > 0:
                    for text in content_text_list:
                        matched = self.highlight_keywords(text)
                        if matched is not None:
                            self.keyword_buff_append(matched, highlight=False)

                if self.summarize_on:
                    return self._summarize_stream_output(msg, content, content_text_list)

                return content
        elif msg_type in ('display_data', 'execute_result'):
            execute_result = content.copy()
            execute_result['execution_count'] = self.execution_count
            self._store_result({'msg_type': msg_type, 'content': execute_result})
            return execute_result
        elif msg_type == 'error':
            error_result = content.copy()
            error_result['execution_count'] = self.execution_count
            self._store_result({'msg_type': msg_type, 'content': error_result})
            return error_result

        return content

    def _summarize_stream_output(self, msg, content, lines):
        # save the first few lines
        if len(self.summarize_header_buff) < self.summarize_header_lines:
            self.summarize_header_buff.extend(lines)
        self._store_last_lines(lines)

        if self.count < self.summarize_start_lines:
            self.count += len(lines)
            stream_content = {'name': content['name'], 'text': content['text']}
        else:
            self._log_buff_flush()

            self.send_clear_content_msg()

            stream_text = u''
            stream_text += self.exec_info.to_stream() + u'----\n'

            stream_text += u'{}\n'.format('\n'.join(self.summarize_header_buff[:self.summarize_header_lines]))
            stream_text += self.display_keyword_buff()
            stream_text += u'...\n'
            stream_text += u'{}'.format('\n'.join(lines[:self.summarize_exec_lines]))

            stream_content = {'name': 'stdout', 'text': stream_text}
        return stream_content

    def _send_last_stdout_stream_text(self):
        self.log.debug('_flush_stdout_stream')
        self.close_files()

        if self.summarize_on:
            self._send_last_summarized_stdout_stream_text()

        self.result_files = []

    def _send_last_summarized_stdout_stream_text(self):
        self.send_clear_content_msg()

        stream_text = u''
        stream_text += self.exec_info.to_stream(len(self.log_history_data)) + u'----\n'

        if self.count < self.summarize_start_lines:
            stream_text += u'\n'.join(self.summarize_last_buff)
        else:
            stream_text += u'{}\n'.format('\n'.join(self.summarize_header_buff[:self.summarize_header_lines]))
            stream_text += self.display_keyword_buff()
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

    def _get_notebook_data(self, parent):
        if 'content' not in parent:
            return None
        content = parent['content']
        if 'lc_notebook_data' not in content:
            return None
        return content['lc_notebook_data']

    def do_shutdown(self, restart):
        self.log.debug('>>>>> do_shutdown')
        self.close_files()

        if self.sender is not None:
            self.log.debug('close fluent logger sender')
            self.sender.close()

        self.log.info('stopping wrapped kernel')
        if hasattr(self, "km"):
            self.km.shutdown_kernel(restart=restart)

        for channel, thread in self.threads.items():
            self.log.info('stopping %s ChannelReaderThread', channel)
            thread.stop()

        return {'status': 'ok', 'restart': restart}


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
