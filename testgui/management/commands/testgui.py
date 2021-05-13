import datetime
import importlib
import os
import pathlib
import sys
from os.path import dirname
from threading import Thread
from typing import List
from unittest import TestCase

import django
import webview
from django.conf import settings
from django.core.management.commands import test
# noinspection PyProtectedMember
from django.test.utils import get_runner

load_time = datetime.datetime.now()


def get_last_mod_time(file_path):
    fname = pathlib.Path(file_path)
    return datetime.datetime.fromtimestamp(fname.stat().st_mtime)


class Api:
    def __init__(self, test_runner, test_labels, old_config):
        self.old_config = old_config
        self.test_labels = test_labels
        self.test_runner = test_runner
        self.window = None
        super().__init__()

    @staticmethod
    def collect_tests(test_runner, test_labels):
        suite = test_runner.build_suite(test_labels)
        return [get_path(test) for test in suite._tests]

    def init_tests(self, window):
        self.tests = self.collect_tests(self.test_runner, self.test_labels)
        self.window = window
        window.evaluate_js(f'initTests({self.tests})')

    def reload_code(self):
        project_folder = dirname(sys.modules['__main__'].__file__)
        modules = list(sys.modules.values())
        print("reloading modules in project folder (except for manage.py, models.py's and admin.py's)...")
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
                self.send_warning(f'Cannot reload __main__ module ({module.__file__})!')
                continue
            if any(s in module.__name__.split('.')[-1] for s in ['admin', 'models']):
                self.send_warning(f'Cannot reload admin/model module {module.__name__}!')
                continue
            print('reloading', module.__name__)
            importlib.reload(module)

    def repopulate_tests(self):
        print('repopulating tests...')
        self.reload_code()
        populate_tests(self.test_runner, self.test_labels)
        self.init_tests(self.window)

    def run_all_tests(self):
        self.reload_code()
        for test in self.tests:
            self.run_test(test)

    def run_selected_tests(self, indices):
        self.reload_code()
        for index in sorted(indices):
            self.run_test(self.tests[index])

    def run_test(self, test):
        if self.window is None:
            raise AssertionError('Please run api.init first')
        th = Thread(target=lambda: self.run_test_job('.'.join(test)))
        th.start()
        th.join()

    def run_test_job(self, test_label):
        try:
            suite = self.test_runner.build_suite((test_label,))
            tests = suite._tests[:]
            results = self.test_runner.run_suite(suite)
            self.send_results(tests, results)
        except Exception as e:
            msg = f'ERROR: Could not run the test, the following error was raised:\n\n{e.args[0]}'
            self.send_result(test_case=test_label, msg=msg, status='error')

    def send_warning(self, msg):
        print(f'WARNING: {msg}')
        msg = msg.replace('"', r'\"').replace('\n', r'\n')
        code = f'setWarning({{ message: "{msg}"}})'
        self.window.evaluate_js(code)

    def send_result(self, test_case, msg, status):
        if isinstance(test_case, str):
            name = test_case
        elif isinstance(test_case, TestCase):
            name = ".".join(get_path(test_case))
        else:
            raise NotImplementedError
        msg = msg.replace('"', r'\"').replace('\n', r'\n')
        code = f'setResult({{name: "{name}", status: "{status}", message: "{msg}"}})'
        self.window.evaluate_js(code)

    def send_results(self, tests, results):
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


class Command(test.Command):
    help = "Runs tests via GUI to accelerate running specific tests."

    def handle(self, *test_labels, **options):
        if options['verbosity'] < 2:
            options['verbosity'] = 2
        # noinspection PyPep8Naming
        TestRunner = get_runner(settings, options['testrunner'])
        test_runner = TestRunner(**options)
        test_runner.setup_test_environment()
        old_config = populate_tests(test_runner, test_labels)
        run_failed = False
        try:
            old_config = self.create_gui(test_runner, test_labels, old_config)
        except Exception:
            run_failed = True
            raise
        finally:
            teardown(old_config, run_failed, test_runner)

    def create_gui(self, test_runner, test_labels, old_config):
        api = Api(test_runner, test_labels, old_config)
        this_file = os.path.dirname(__file__)
        testgui_path = this_file[:-len('/management/commands')]
        window = webview.create_window('TestGUI',
                                       os.path.join(testgui_path, 'assets/index.html'),
                                       js_api=api,
                                       min_size=(600, 450),
                                       )
        webview.start(api.init_tests, window, debug=True)
        return api.old_config


def get_path(test: TestCase) -> List[str]:
    path = test.__module__.split('.')
    # noinspection PyProtectedMember
    path += [test.__class__.__name__, test._testMethodName]
    return path


def teardown(old_config, run_failed, test_runner):
    try:
        test_runner.teardown_databases(old_config)
        test_runner.teardown_test_environment()
    except Exception:
        # Silence teardown exceptions if an exception was raised during
        # runs to avoid shadowing it.
        if not run_failed:
            raise


def populate_tests(test_runner, test_labels):
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
    return old_config
