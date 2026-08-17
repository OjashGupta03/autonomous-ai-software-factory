from __future__ import annotations

import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk


class File(TimestampMixin, Base):
    """The canonical, versioned store for generated project files. Tools
    (file_writer) and agents mutate this table; the sandbox executor reads
    from it to materialise a workspace on disk. `content_hash` lets the
    context manager dedupe/cache without re-reading full file bodies."""

    __tablename__ = "files"
    __table_args__ = (UniqueConstraint("project_id", "path", "version", name="uq_file_path_version"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by_task_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )


class ArtifactType(str):
    FILE = "file"
    DIFF = "diff"
    DOCUMENT = "document"
    SUMMARY = "summary"
    TEST_REPORT = "test_report"


class Artifact(TimestampMixin, Base):
    """A pointer to something a task produced. Intentionally does NOT
    duplicate file content: `file_id` + the file's `version` is enough to
    reconstruct it. This is what lets agent-to-agent messages say 'see
    artifact X' instead of pasting file bodies (docs/06, docs/18)."""

    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    content_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
