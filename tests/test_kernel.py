import re
import unittest

from logging import getLogger, StreamHandler, DEBUG, INFO

from lc_wrapper import kernel


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
