import re
import unittest

from logging import getLogger, StreamHandler, DEBUG, INFO

from lc_wrapper import kernel

from datetime import datetime
import dateutil
import os 
import pickle
import test.support
import tempfile

log = getLogger(__name__)

class DummyKernel(kernel.BufferedKernelBase):

    def _get_wrapped_kernel_name(self):
        return 'python3'


class TestKernel(unittest.TestCase):

    def setUp(self):
        self.instance = DummyKernel(log=log)
        self.test_mask_target = '''
a@b.com
1234567890
aaa bbb ccc
日本語
'''

    def tearDown(self):
        self.instance.log_file_object=None
        self.instance.do_shutdown(False)

    def test_should_not_mask_without_config(self):
        target = self.test_mask_target

        masked = self.instance._mask_lines(target)

        self.assertEqual(masked, target)

    def test_mask_not_matched(self):
        pattern = re.compile(r'nothing')
        target = self.test_mask_target
        self.instance.masking_pattern = pattern

        masked = self.instance._mask_lines(target)

        self.assertEqual(masked, target)

    def test_mask_something(self):
        pattern_list = [
            'aaa',
            '日本',
            '語',
            '[0-9]+',
            '[a-z]+@[a-z]+.com',
        ]
        target = self.test_mask_target

        for pattern in pattern_list:
            self.instance.masking_pattern = pattern

            masked = self.instance._mask_lines(target)

            self.assertNotEqual(masked, target)
            self.assertIn('*', masked)

    def test_mask_numbers(self):
        pattern = r'[0-9]+'
        target = self.test_mask_target
        self.instance.masking_pattern = pattern

        masked = self.instance._mask_lines(target)
        expected = '''
a@b.com
**********
aaa bbb ccc
日本語
'''
        self.assertEqual(masked, expected)

    def test_mask_email(self):
        pattern = '[a-z]+@[a-z\.]+.com'
        target = self.test_mask_target
        self.instance.masking_pattern = pattern

        masked = self.instance._mask_lines(target)
        expected = '''
*******
1234567890
aaa bbb ccc
日本語
'''

        self.assertEqual(masked, expected)

    def test_mask_binary(self) : 
        pattern='passwa(\-)*d'
        target='\x1b[0;31m----------\x1b[0mpasswa---d\x1b[0;34m----------\x1b[0m'
        result='\x1b[0;31m----------\x1b[0m**********\x1b[0;34m----------\x1b[0m'

        self.instance.masking_pattern = pattern
        masked=self.instance._mask_lines(target)

        self.assertEqual(masked, result)        

    def test_read_mask_flag_from_env(self):
        self.set_env_LOG_MASKING_KEY('on')
        self.instance.notebook_path=self.create_dummy_notebook_home("off")
        self.prepare_dummy_kernel_settings()

        env = self.instance._get_config() 

        if kernel.LOG_MASKING_KEY in env:
            flag = env.get(kernel.LOG_MASKING_KEY)
        else :
            flag=None

        self.delete_dummy_notebook_home()
        
        self.assertEqual(flag, 'on')        

    def test_read_mask_flag_from_config_file(self):
        self.set_env_LOG_MASKING_KEY("")
        self.instance.notebook_path=self.create_dummy_notebook_home("off")
        self.prepare_dummy_kernel_settings()

        env = self.instance._get_config() 

        if kernel.LOG_MASKING_KEY in env:
            flag = env.get(kernel.LOG_MASKING_KEY)
        else :
            flag=None

        self.delete_dummy_notebook_home()
        self.assertEqual(flag, 'off')

    def test_load_env_mask_flag_use_config_(self):
        self.set_env_LOG_MASKING_KEY("")
        self.instance.notebook_path=self.create_dummy_notebook_home("off")
        self.prepare_dummy_kernel_settings()

        env = {}
        env[kernel.MASKING_KEY]='passwa(\-)*d'
        env[kernel.LOG_MASKING_KEY]='off'

        self.instance._load_env(env) 

        flag=self.instance.log_mask # on as default

        self.delete_dummy_notebook_home()

        self.assertEqual(flag, 'off')

    def test_load_env_mask_flag_use_default_env_not_found(self):
        self.set_env_LOG_MASKING_KEY("")
        self.instance.notebook_path=self.create_dummy_notebook_home("")
        self.prepare_dummy_kernel_settings()

        env = {}
        env[kernel.MASKING_KEY]='passwa(\-)*d'

        self.instance._load_env(env) 

        flag=self.instance.log_mask # on as default

        self.delete_dummy_notebook_home()

        self.assertEqual(flag, 'on')

    def test_load_env_mask_flag_use_default_env_not_defined(self):
        self.set_env_LOG_MASKING_KEY("")
        self.instance.notebook_path=self.create_dummy_notebook_home("")
        self.prepare_dummy_kernel_settings()

        env = {}

        self.instance._load_env(env) 

        flag=self.instance.log_mask # on as default

        self.delete_dummy_notebook_home()

        self.assertEqual(flag, 'on')

    # subfunctions
    def create_dummy_notebook_home(self, v_lc_wrapper_mask_log):
        self.work_dir=tempfile.TemporaryDirectory()

        self.reg_pattern_file =os.path.join(self.work_dir.name, kernel.IPYTHON_DEFAULT_PATTERN_FILE)
        reg_pattern =kernel.IPYTHON_DEFAULT_PATTERN
        if not os.path.exists(self.reg_pattern_file):
            f = open(self.reg_pattern_file, 'w')
            f.write(reg_pattern)
            f.close()
        self.instance.keyword_pattern_file_paths = [self.reg_pattern_file]

        self.config_file=os.path.join(self.work_dir.name, ".lc_wrapper")
        f = open(self.config_file, 'a')
        if len(v_lc_wrapper_mask_log) == 0 :
            f.write("\n")
        else :
            f.write("lc_wrapper_mask_log=" + v_lc_wrapper_mask_log + "\n")
        f.close()
        self.instance.configfile_paths = [self.config_file]

        return self.work_dir.name

    def delete_dummy_notebook_home(self):
        self.work_dir.cleanup()
        return

    def set_env_LOG_MASKING_KEY(self, v_LOG_MASKING_KEY): 
        if (len(v_LOG_MASKING_KEY)>0) :
            test.support.EnvironmentVarGuard().set(kernel.LOG_MASKING_KEY,v_LOG_MASKING_KEY)
        else:
            if (kernel.LOG_MASKING_KEY in os.environ) :
                test.support.EnvironmentVarGuard().unset(kernel.LOG_MASKING_KEY)
        return

    def prepare_dummy_kernel_settings(self) :
        self.instance.summarize_start_lines = 50
        self.instance.summarize_header_lines = 20
        self.instance.summarize_exec_lines = 1
        self.instance.summarize_footer_lines = 20

        self.instance.log_history_file_path = None

