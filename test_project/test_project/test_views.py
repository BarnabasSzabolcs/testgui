import time
from unittest import TestCase

from test_project.views import dummy


class ViewsTestCase(TestCase):
    def test_dummy(self):
        self.assertEqual(dummy(), 'dummy')

    def test_dummy2(self):
        time.sleep(2)
        # return
        self.assertEqual(dummy(), 'dummy2')


class AnotherTestCase(TestCase):
    def test_dummy3(self):
        # return
        self.assertEqual(error)
        self.assertEqual(dummy(), 'dummy3')

