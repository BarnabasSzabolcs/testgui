import datetime
import importlib
import pathlib
import sys
import unittest
from os.path import dirname
from threading import Thread
from types import ModuleType
from typing import List, Tuple, Any
from unittest import TestCase, TestSuite

import django
import webview

from ansi2html import Ansi2HTMLConverter

from testgui import TEST_GUI_INDEX_PATH

load_time = datetime.datetime.now()


def set_load_time(time):
    global load_time
    load_time = time


def get_last_mod_time(file_path):
    fname = pathlib.Path(file_path)
    return datetime.datetime.fromtimestamp(fname.stat().st_mtime)


def html_from_ansi(ansi: str) -> str:
    """
    include ansi.min.css
    :param ansi:
    :return:
    """
    ansi = ansi.replace('<', '&lt;').replace('>', '&gt;')
    conv = Ansi2HTMLConverter(linkify=True, inline=True, scheme="solarized")
    html = conv.convert(ansi, full=False)
    return html


class Api:
    def populate_tests(self):
        raise NotImplementedError

    def __init__(self, test_runner, test_labels=None, old_config=None, suite=None):
        self.old_config = old_config
        self.test_labels = test_labels
        self.test_runner = test_runner
        self.suite = suite or test_runner.build_suite(test_labels)
        self.window = None

    def collect_tests(self) -> List[str]:
        # noinspection PyProtectedMember
        return [get_path(test) for test in self.suite._tests]

    def init_tests(self, window):
        self.window = window
        window.evaluate_js(f'app.initTests({self.collect_tests()})')

    def reload_code(self):
        project_folder = dirname(sys.modules['__main__'].__file__)
        modules = list(sys.modules.values())
        print("reloading modules in project folder (except for manage.py, models.py's and admin.py's)...")
        then = datetime.datetime.now()
        for module in modules:
            if not hasattr(module, '__file__'):
                continue
            if not isinstance(module.__file__, str):
                continue
            if 'lib/python' in module.__file__:
                continue
            if not module.__file__.startswith(project_folder):
                continue
            if load_time > get_last_mod_time(module.__file__):
                continue
            if module.__name__ == '__main__':
                with open(module.__file__, 'r') as f:
                    code = f.read()
                    myglobals = dict()
                    exec(code, myglobals)
                    for key, value in myglobals.items():
                        if key == '__builtins__':
                            continue
                        if isinstance(value, ModuleType):
                            continue
                        if hasattr(value, '__module__'):
                            value.__module__ = '__main__'
                        setattr(module, key, value)
                self.send_warning(f'Reloaded __main__ module ({module.__file__})')
                continue
            if any(s in module.__name__.split('.')[-1] for s in ['admin', 'models']):
                self.send_warning(f'Cannot reload admin/model module {module.__name__}!')
                continue
            print('reloading', module.__name__)
            importlib.reload(module)
        set_load_time(then)

    def repopulate_tests(self):
        print('repopulating tests...')
        self.reload_code()
        self.populate_tests()
        self.init_tests(self.window)

    def run_all_tests(self):
        self.reload_code()
        # noinspection PyProtectedMember
        for test in self.suite._tests:
            self.run_test(test)

    def run_selected_tests(self, indices):
        self.reload_code()
        for index in sorted(indices):
            # noinspection PyProtectedMember
            self.run_test(self.suite._tests[index])

    def run_test(self, test_case: TestCase):
        if self.window is None:
            raise AssertionError('Please run api.init first')
        th = Thread(target=lambda: self.run_test_job(test_case))
        th.start()
        th.join()

    def run_test_job(self, test_case: TestCase):
        try:
            if hasattr(self.test_runner, 'run_suite'):
                results = self.test_runner.run_suite(test_case)
            else:
                results = self.test_runner.run(test_case)
            self.send_results([test_case], results)
        except Exception as e:
            msg = f'ERROR: Could not run the test, the following error was raised:\n\n{e.args[0]}'
            self.send_result(test_case=test_case, msg=msg, status='error')

    def send_warning(self, msg: str):
        print(f'WARNING: {msg}')
        msg = msg.replace('"', r'\"').replace('\n', r'\n')
        code = f'app.setWarning({{ message: "{msg}"}})'
        self.window.evaluate_js(code)

    def send_result(self, test_case: TestCase, msg: str, status: str):
        name = get_path(test_case)
        msg = msg.replace('File "<string>"', f"File \"{sys.modules['__main__'].__file__}\"")
        msg = html_from_ansi(msg)
        msg = msg.replace('"', r'\"').replace('\n', r'\n')
        code = f'app.setResult({{name: "{name}", status: "{status}", message: "{msg}"}})'
        self.window.evaluate_js(code)

    def send_results(self, tests: List[TestCase], results):
        unsuccessful = set()

        for test, msg in results.failures:
            self.send_result(test, msg, status='failure')
            unsuccessful.add(test)
        for test, msg in results.errors:
            self.send_result(test, msg, status='error')
            unsuccessful.add(test)
        for test in tests:
            if test in unsuccessful:
                continue
            self.send_result(test, '', status='success')


class DjangoTestApi(Api):

    def populate_tests(self):
        _, self.suite = populate_tests(self.test_runner, self.test_labels)


class UnitTestApi(Api):
    def __init__(self, test_runner, suite):
        super().__init__(test_runner=test_runner, suite=suite)

    def reload_code(self):
        super().reload_code()
        self.populate_tests()

    def populate_tests(self):
        test_program = unittest.TestProgram()
        # noinspection PyUnresolvedReferences,PyProtectedMember
        self.suite = test_program.test._tests[0]


def run_django_test_gui(test_runner, test_labels):
    test_runner.setup_test_environment()
    old_config, _ = populate_tests(test_runner, test_labels)
    run_failed = False
    try:
        api = DjangoTestApi(test_runner, test_labels, old_config)
        old_config = create_test_gui(api)
    except Exception:
        run_failed = True
        raise
    finally:
        teardown(old_config, run_failed, test_runner)


def create_test_gui(api):
    window = webview.create_window(
        'TestGUI',
        TEST_GUI_INDEX_PATH,
        js_api=api,
        min_size=(600, 450))
    webview.start(api.init_tests, window, debug=True)
    return api.old_config


def get_path(test: TestCase) -> str:
    path = test.__module__.split('.')
    # noinspection PyProtectedMember
    path += [test.__class__.__name__, test._testMethodName]
    return '.'.join(path)


def teardown(old_config, run_failed, test_runner):
    # noinspection PyBroadException
    try:
        test_runner.teardown_databases(old_config)
        test_runner.teardown_test_environment()
    except Exception:
        # Silence teardown exceptions if an exception was raised during
        # runs to avoid shadowing it.
        if not run_failed:
            raise


def populate_tests(test_runner, test_labels) -> Tuple[Any, TestSuite]:
    suite = test_runner.build_suite(test_labels)
    # modified version of DiscoverRunner's run_tests
    databases = test_runner.get_databases(suite)
    old_config = test_runner.setup_databases(aliases=databases)
    try:
        if django.VERSION[0] == 2:
            test_runner.run_checks()
        else:
            test_runner.run_checks(databases)
    except Exception:
        run_failed = True
        teardown(old_config, run_failed, test_runner)
        raise
    return old_config, suite
