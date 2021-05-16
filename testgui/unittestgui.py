"""
Drop-in replacement for unittests. Replace

if __name__ == '__main__':
    unittest.main()

with

if __name__ == '__main__':
    unittestgui.main()

"""

import unittest
import unittest.mock
import unittest.runner

from testgui.gui import create_test_gui, UnitTestApi


def main():
    with unittest.mock.patch.object(unittest.TestProgram, 'runTests'):
        test_program = unittest.TestProgram()
        test_runner = unittest.runner.TextTestRunner
        try:
            # noinspection PyUnresolvedReferences
            test_runner = test_runner(
                verbosity=test_program.verbosity,
                failfast=test_program.failfast,
                buffer=test_program.buffer,
                warnings=test_program.warnings,
                tb_locals=test_program.tb_locals)
        except TypeError:
            # didn't accept the tb_locals argument
            test_runner = test_runner(
                verbosity=test_program.verbosity,
                failfast=test_program.failfast,
                buffer=test_program.buffer,
                warnings=test_program.warnings)
        # noinspection PyUnresolvedReferences,PyProtectedMember
        api = UnitTestApi(test_runner=test_runner, suite=test_program.test._tests[0])
        create_test_gui(api)
