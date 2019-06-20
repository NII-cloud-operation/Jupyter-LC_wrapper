from datetime import datetime
import dateutil
import os


class ExecutionInfo(object):
    def __init__(self, code, server_signature=None, notebook_data=None):
        self.code = code
        self.log_path = None
        self.start_time = datetime.now(dateutil.tz.tzlocal()).strftime('%Y-%m-%d %H:%M:%S(%Z)')
        self.end_time = None
        self.file_size = 0
        self.keyword_buff_size = None
        self.server_signature = server_signature
        self.uid = os.getuid()
        self.gid = os.getgid()
        if notebook_data is not None:
            self.notebook_path = notebook_data.get('notebook_path', None)
            self.lc_notebook_meme = notebook_data.get('lc_notebook_meme', {}).get('current', None)
        else:
            self.notebook_path = None
            self.lc_notebook_meme = None
        self.execute_reply_status = None

    def finished(self, keyword_buff_size):
        self.end_time = datetime.now(dateutil.tz.tzlocal()).strftime('%Y-%m-%d %H:%M:%S(%Z)')
        self.keyword_buff_size = keyword_buff_size

    def to_stream(self, history_count=None):
        return self.to_stream_header(history_count) + self.to_stream_footer()

    def to_stream_header(self, history_count=None):
        stream_text = u''
        if self.log_path is not None:
            if history_count is not None:
                stream_text += u'path: {} ({} logs recorded)\n'.format(self.log_path, history_count)
            else:
                stream_text += u'path: {}\n'.format(self.log_path)
        stream_text += u'start time: {}\n'.format(self.start_time)

        return stream_text

    def to_logfile_header(self):
        stream_text = u''
        if self.log_path is not None:
            stream_text += u'path: {}\n'.format(self.log_path)
        if self.notebook_path is not None:
            stream_text += u'notebook_path: {}\n'.format(self.notebook_path)
        if self.lc_notebook_meme:
            stream_text += u'lc_notebook_meme: {}\n'.format(self.lc_notebook_meme)
        if self.server_signature is not None:
            stream_text += u'server_signature: {}\n'.format(self.server_signature)
        if self.uid is not None:
            stream_text += u'uid: {}\n'.format(self.uid)
        if self.gid is not None:
            stream_text += u'gid: {}\n'.format(self.gid)
        stream_text += u'start time: {}\n'.format(self.start_time)

        return stream_text

    def to_stream_footer(self):
        stream_text = u''
        if self.end_time is not None:
            stream_text += u'end time: {}\n'.format(self.end_time)
        stream_text += u'output size: {} bytes\n'.format(self.file_size)
        if self.keyword_buff_size is not None:
            stream_text += u'{} chunks with matched keywords or errors\n'.format(self.keyword_buff_size)
        return stream_text

    def to_logfile_footer(self):
        stream_text = u''
        if self.end_time is not None:
            stream_text += u'end time: {}\n'.format(self.end_time)
        if self.keyword_buff_size is not None:
            stream_text += u'{} chunks with matched keywords or errors\n'.format(self.keyword_buff_size)
        return stream_text

    def to_log(self):
        log = {'code': self.code,
               'path': self.log_path,
               'start': self.start_time,
               'end': self.end_time,
               'size': self.file_size,
               'server_signature': self.server_signature,
               'uid': self.uid,
               'gid': self.gid,
               'notebook_path': self.notebook_path,
               'lc_notebook_meme': self.lc_notebook_meme,
               'execute_reply_status': self.execute_reply_status
              }
        return log
