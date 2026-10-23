"""Shared business logic for every Beacon Lambda: models, state machine, maths, checks, storage."""

import os

VERSION = os.environ.get("BEACON_VERSION", "dev")
