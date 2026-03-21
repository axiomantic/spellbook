"""Declarative bases for each database.

Each SQLite database gets its own DeclarativeBase so models can be
defined independently and migrations can target a specific database.
"""

from sqlalchemy.orm import DeclarativeBase


class SpellbookBase(DeclarativeBase):
    """Base class for spellbook.db models."""
    pass


class FractalBase(DeclarativeBase):
    """Base class for fractal.db models."""
    pass


class ForgedBase(DeclarativeBase):
    """Base class for forged.db models."""
    pass


class CoordinationBase(DeclarativeBase):
    """Base class for coordination.db models."""
    pass
