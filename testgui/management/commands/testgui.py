from django.conf import settings
from django.core.management.commands import test as django_test_command
from django.test.utils import get_runner

from testgui.gui import run_django_test_gui


class Command(django_test_command.Command):
    help = "Runs tests via GUI to accelerate running specific tests."

    def handle(self, *test_labels, **options):
        if options['verbosity'] < 2:
            options['verbosity'] = 2
        # noinspection PyPep8Naming
        TestRunner = get_runner(settings, options['testrunner'])
        test_runner = TestRunner(**options)
        run_django_test_gui(test_runner, test_labels)
