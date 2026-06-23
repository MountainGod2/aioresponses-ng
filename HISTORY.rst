=======
History
=======
0.8.0 (2026-06-22)
-------------------
* Forked as aioresponses-ng from aioresponses
* Fixed aiohttp 3.10+ compatibility (stream_reader_factory loop parameter)
* Fixed aiohttp 3.14+ compatibility (stream_writer argument)
* Added async context manager support (__aenter__ / __aexit__)
* Migrated packaging to pyproject.toml with hatchling
* Replaced flake8 and tox with ruff and uv
* Dropped support for Python <3.10 and aiohttp <3.9
* Modernized type hints to Python 3.10+ style

0.1.0 (2016-10-17)
------------------

* initial commit
