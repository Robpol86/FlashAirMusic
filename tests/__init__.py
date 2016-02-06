"""Importable objects shared by test modules."""

import datetime

import py

HERE = py.path.local(__file__).dirpath()
TZINFO = datetime.timezone(datetime.timedelta(hours=-8))  # Tests are written with Pacific Time in mind.
