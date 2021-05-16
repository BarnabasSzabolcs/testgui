import unittest

from testgui import unittestgui


class SampleTestCase(unittest.TestCase):

    def test_sample(self):
        self.assertTrue(False)


if __name__ == '__main__':
    unittestgui.main()
    # unittest.main()
