"""
Cross-dialect UUID column type.

`sqlalchemy.dialects.postgresql.UUID` only has a DDL compiler registered
for the postgresql dialect - using it directly in a model means
`Base.metadata.create_all()` raises a CompileError against any other
backend, including the in-memory SQLite database backend/tests/conftest.py
uses so the test suite can run without a live Postgres instance. `GUID`
is the standard SQLAlchemy recipe for this: native UUID on Postgres,
CHAR(32) hex-string storage everywhere else, transparent uuid.UUID
in/out on both. Every model uses this instead of importing
postgresql.UUID directly - see app/db/base.py::uuid_pk().
"""
from __future__ import annotations

import uuid

from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import CHAR, TypeDecorator


class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(str(value)).hex
        return value.hex

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)
