=======
History
=======

0.8.2 (2026-07-05)
-------------------

* **Breaking change**: updated assertion APIs in ``aioresponses`` to support
  partial-argument matching via ``args_to_match`` and corrected call matching
  semantics for ``assert_any_call``
* Fixed call-count assertions to count total recorded calls across all
  method/URL keys (not just grouped buckets)
* Fixed ``assert_not_called`` message count to reflect actual recorded requests
* Updated ``__version__`` to use package metadata at runtime via
  ``importlib.metadata.version("aioresponses-ng")`` with a safe fallback when
  metadata is unavailable
* Refactored the test suite from legacy unittest/ddt helpers to modern
  ``pytest`` patterns, removed obsolete compatibility tests, and expanded
  assertion/callback coverage
* Tightened linting/tooling configuration (additional Ruff rule sets,
  pytest-asyncio defaults) and refreshed GitHub Actions workflows with stricter
  permissions and updated pinned actions

0.8.1 (2026-06-26)
-------------------

* Fixed large payload handling (bodies > 64 KB) via ``_MockResponseHandler``
  subclass — replaces ``pause_reading`` no-op without importing test
  infrastructure into library code
* Fixed ``raise_for_status`` callable to match aiohttp's own type contract
  (``Callable[[ClientResponse], Awaitable[None]]``) — sync callables are no
  longer silently accepted
* Moved ``AIOHTTP_VERSION``, ``URL``, and ``Pattern`` out of ``compat`` and
  into ``core`` where they are used; ``compat`` now only exports
  ``merge_params``, ``normalize_url``, and ``stream_reader_factory``
* Removed ``unittest.mock.Mock`` usage from ``core`` (moved to subclass approach)
* Minor code cleanup: collapsed intermediate variables, fixed ``else/if`` →
  ``elif``, removed redundant ``else: break`` after ``continue``

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