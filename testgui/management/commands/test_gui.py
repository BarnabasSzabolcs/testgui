import importlib
import sys
from os.path import dirname
from threading import Thread
from typing import List
from unittest import TestCase

import webview
from django.conf import settings
from django.core.management.commands import test
# noinspection PyProtectedMember
from django.test.utils import get_runner


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

    @staticmethod
    def reload_code():
        project_folder = dirname(sys.modules['__main__'].__file__)
        modules = list(sys.modules.values())
        print('reloading modules in project folder (except for manage.py)...')
        for module in modules:
            if not hasattr(module, '__file__'):
                continue
            if not isinstance(module.__file__, str):
                continue
            if 'lib/python' in module.__file__:
                continue
            if module.__name__ == '__main__':
                continue
            if not module.__file__.startswith(project_folder):
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

        suite = self.test_runner.build_suite((test_label,))
        tests = suite._tests[:]
        results = self.test_runner.run_suite(suite)
        self.send_results(tests, results)

    def print_message(self, msg):
        msg = msg.replace('"', r'\"')
        # self.original_write_out(msg)
        self.window.evaluate_js(f'addLog("{msg}")')

    def print_error(self, msg):
        msg = msg.replace('"', r'\"')
        # self.original_write_error(msg)
        self.window.evaluate_js(f'addError("{msg}")')

    def send_results(self, tests, results):
        unsuccessful = set()

        def send(test_case, msg, status):
            name = ".".join(get_path(test_case))
            msg = msg.replace('"', r'\"').replace('\n', r'\n')
            code = f'setResult({{name: "{name}", status: "{status}", message: "{msg}"}})'
            self.window.evaluate_js(code)

        for test, msg in results.failures:
            send(test, msg, status='failure')
            unsuccessful.add(test)
        for test, msg in results.errors:
            send(test, msg, status='error')
            unsuccessful.add(test)
        for test in tests:
            if test in unsuccessful:
                continue
            send(test, '', status='success')


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
        window = webview.create_window('TestGUI',
                                       'testgui/assets/index.html',
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
        with test_runner.time_keeper.timed('Total database teardown'):
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
    with test_runner.time_keeper.timed('Total database setup'):
        old_config = test_runner.setup_databases(aliases=databases)
    try:
        test_runner.run_checks(databases)
    except Exception:
        run_failed = True
        teardown(old_config, run_failed, test_runner)
        raise
    return old_config, suite
