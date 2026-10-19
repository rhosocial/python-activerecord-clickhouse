# tests/rhosocial/activerecord_clickhouse_test/feature/backend/expression/conftest.py
"""The expression test area: construction → render, no I/O, always parallel.

This directory holds every expression-level test of this backend -- the
round-trip matrix, the literal spellings, the signature and function-entry
checks. The org rules (expression-dialect §12) give the area three
properties, and the tests here are written to all three:

* every case carries its own dialect instance and shares no mutable state;
* nothing opens a connection, creates a database, or touches the filesystem,
  so the whole area runs without the scenario server;
* the cases are therefore independent, and parallelism is the default
  scheduling, not an option.

The parallel default itself cannot live in a conftest: pytest-xdist reads
its worker count before any conftest loads, so a conftest cannot inject
``-n``. The default is wired one level out, in the repository-local plugin
``tests/plugins/expression_xdist.py`` (registered from ``pyproject.toml``),
which appends ``-n auto --dist=loadgroup`` when the invocation names only
this directory and the caller has not chosen a worker count itself. The
plugin is the availability check too: with pytest-xdist absent it enables
nothing and says so.

Serial cases: a test that genuinely cannot share a worker marks
``xdist_group`` explicitly and states the reason beside the mark. None does
today -- no case here has I/O to serialize around. ``--dist=loadscope`` and
``--dist=loadfile`` are not used: they bind whole modules together and would
hide exactly the case-to-case dependencies parallelism exists to expose.
"""
