from datetime import datetime
import dateutil


def parse_execution_info_log(log):
    r = ExecutionInfo(log['code'])
    r.log_path = log['path']
    r.start_time = log['start']
    r.end_time = log['end']
    r.file_size = log['size']
    return r


class ExecutionInfo(object):
    def __init__(self, code):
        self.code = code
        self.log_path = None
        self.start_time = datetime.now(dateutil.tz.tzlocal()).strftime('%Y-%m-%d %H:%M:%S(%Z)')
        self.end_time = None
        self.file_size = 0
        self.keyword_buff_size = None

    def finished(self, keyword_buff_size):
        self.end_time = datetime.now(dateutil.tz.tzlocal()).strftime('%Y-%m-%d %H:%M:%S(%Z)')
        self.keyword_buff_size = keyword_buff_size

    def to_stream(self):
        return self.to_stream_header() + self.to_stream_footer()

    def to_stream_header(self):
        stream_text = u''
        if self.log_path is not None:
            stream_text += u'path: {}\n'.format(self.log_path)
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

    def to_log(self):
        log = {'code': self.code,
               'path': self.log_path,
               'start': self.start_time,
               'end': self.end_time,
               'size': self.file_size}
        return log
