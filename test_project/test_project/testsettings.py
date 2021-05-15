# noinspection PyUnresolvedReferences
from django.test.runner import DiscoverRunner

# noinspection PyUnresolvedReferences
from test_project.settings import *

TEST_RUNNER = 'redgreenunittest.django.runner.RedGreenDiscoverRunner'
