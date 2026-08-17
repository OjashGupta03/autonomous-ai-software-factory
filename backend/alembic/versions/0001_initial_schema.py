"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-01-15 00:00:00

Deliberately generated from `Base.metadata` rather than hand-authored
`op.create_table()` calls for every one of the 18 tables in app/models.
This repository was built without a live Postgres connection to run
`alembic revision --autogenerate` against, and hand-transcribing ~150
columns/FKs/indexes from the model files by hand is exactly the kind of
error-prone busywork that autogenerate exists to replace. Using the
models' own metadata as the single source of truth guarantees this
migration cannot drift out of sync with app/models - it is generated
from the same objects at every run, not a manually-maintained mirror of
them.

Once you have a running database, running
    alembic revision --autogenerate -m "checkpoint"
immediately after `alembic upgrade head` should produce an EMPTY
migration - that's the sanity check that this file and app/models truly
agree (see docs/20-local-development.md and docs/24-troubleshooting.md).
Every migration after this one should be a normal autogenerate diff.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.db.base import Base
    import app.models  # noqa: F401 - registers every model class on Base.metadata

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from app.db.base import Base
    import app.models  # noqa: F401

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
