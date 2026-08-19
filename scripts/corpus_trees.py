#!/usr/bin/env python3
"""Shared corpus-tree memberships for the repository's checkers and tests.

Scripts under ``scripts/`` and tests under ``tests/`` import from here so that
a tree added to the repository is added to each membership deliberately,
rather than being missed in one hardcoded tuple out of several.

These sets are DELIBERATELY unequal. The inequality is the content: each name
answers a different question, and collapsing them onto one another would
silently change what a checker scans or reports. A consumer imports the set
whose REASON matches its own, never the set that happens to have the right
members today.
"""

DOCUMENTED_TREES = ("skills", "commands", "agents", "rules")
"""Trees whose sources generate a page under ``docs/`` and an mkdocs nav entry.

Membership reason: ``generate_docs.py`` mirrors each of these into
``docs/<tree>/``. A tree belongs here when its sources are published, so
prose scanned for references and docs pages swept for orphans both follow
this set.
"""

ENUMERABLE_TREES = DOCUMENTED_TREES + ("patterns", "profiles", "extensions")
"""Trees that constitute the repository corpus a checker might enumerate.

Membership reason: these are the trees holding authored corpus content, as
opposed to code (``scripts``, ``hooks``, ``installer``), tests, or generated
output (``docs``). This is a DETECTION VOCABULARY -- naming a member is what
marks a file as corpus-facing. It is not a list of scan roots, and a consumer
that walks directories wants its own explicit roots instead.

``patterns``, ``profiles``, and ``extensions`` extend ``DOCUMENTED_TREES``
because they are corpus content that ships without a generated docs page.
"""

README_ARTIFACT_KINDS = ("skills", "commands", "agents")
"""Artifact kinds that have a README table and README link-reference entries.

Membership reason: README.md has a section and a ``(N total)`` table for each
of these. ``rules`` is ABSENT because README has no Rules section -- there is
no table to check a rule against, so a README-table check over ``rules``
would have nothing to read. Reverse checks that read ``docs/`` rather than
README are not bounded by this set; they follow ``DOCUMENTED_TREES``.
"""
