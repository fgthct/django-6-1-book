"""Settings for the test suite: development settings, whatever the environment says."""

import os

os.environ.setdefault("DEBUG", "1")

from .settings import *  # noqa: E402, F403
