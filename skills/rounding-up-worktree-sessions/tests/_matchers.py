"""Shared argument-matcher helpers for the roundup test suite.

Consolidates the ``_IsInstance`` matcher that was previously duplicated in
``test_reorient_exec.py`` and ``test_worktree_index.py``. Stdlib-only.
"""


class _IsInstance:
    """Argument matcher: equals any instance of ``cls``.

    Used in tripwire ``assert_call(raised=...)`` to match the exception
    instance recorded for a ``.raises()`` side effect without pinning the
    exact object identity.
    """

    def __init__(self, cls):
        self._cls = cls

    def __eq__(self, other):
        return isinstance(other, self._cls)

    def __repr__(self):
        return f"_IsInstance({self._cls.__name__})"
