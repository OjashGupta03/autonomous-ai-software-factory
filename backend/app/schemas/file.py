from __future__ import annotations

import uuid

from app.schemas.common import TimestampedSchema


class FileRead(TimestampedSchema):
    project_id: uuid.UUID
    path: str
    content: str
    version: int


class FileMeta(TimestampedSchema):
    """Listing view - deliberately excludes `content` so the file tree can
    be fetched cheaply; full content is a separate GET by id."""
    project_id: uuid.UUID
    path: str
    version: int


class ArtifactRead(TimestampedSchema):
    project_id: uuid.UUID
    task_id: uuid.UUID | None
    artifact_type: str
    file_id: uuid.UUID | None
    content_ref: str | None
