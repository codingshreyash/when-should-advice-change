"""Warranted decision revision: an exploratory study of premise-aware search.

See ``research/warranted_revision/README.md`` for the research question and
``PROTOCOL.md`` for the fixed design. Inference code (``prompts``, ``parsing``,
``scoring``, ``conditions``, ``runner``, ``backends``) never imports gold-label modules;
``tests/test_leakage.py`` enforces this.
"""

__version__ = "0.1.0"
