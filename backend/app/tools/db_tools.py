"""
DB-backed tools - operate on the project's versioned `files` table via an
async SQLAlchemy session. None of these execute code, so they run
directly (no sandbox needed): reading/writing/searching text is not a
security boundary the way running it is.

Each tool is constructed per agent-run with its db session + project_id
already bound, so the LLM-facing tool-call signature only needs the
"business" arguments (path, content, pattern, ...).
"""
from __future__ import annotations

import difflib
import fnmatch
import hashlib
import json
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File
from app.tools.base import Tool, ToolResult, timed


async def _latest_files(db: AsyncSession, project_id: uuid.UUID) -> dict[str, File]:
    """Latest version of every path in the project, as {path: File}."""
    result = await db.execute(select(File).where(File.project_id == project_id))
    latest: dict[str, File] = {}
    for f in result.scalars().all():
        current = latest.get(f.path)
        if current is None or f.version > current.version:
            latest[f.path] = f
    return latest


class FileReaderTool(Tool):
    name = "file_reader"
    description = "Read the current content of a file in the project workspace by path."
    parameters_schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }

    def __init__(self, db: AsyncSession, project_id: uuid.UUID):
        self.db = db
        self.project_id = project_id

    async def run(self, path: str) -> ToolResult:
        with timed() as t:
            files = await _latest_files(self.db, self.project_id)
            f = files.get(path)
        if f is None:
            return ToolResult(success=False, error=f"No such file: {path}", execution_time_ms=t["elapsed_ms"])
        return ToolResult(
            success=True,
            output={"path": path, "content": f.content, "version": f.version},
            execution_time_ms=t["elapsed_ms"],
        )


class FileWriterTool(Tool):
    name = "file_writer"
    description = "Create or overwrite a file in the project workspace. Automatically versioned."
    parameters_schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path", "content"],
    }

    def __init__(self, db: AsyncSession, project_id: uuid.UUID, created_by_task_id: uuid.UUID | None = None):
        self.db = db
        self.project_id = project_id
        self.created_by_task_id = created_by_task_id

    async def run(self, path: str, content: str) -> ToolResult:
        with timed() as t:
            if r"\n" in content and "\n" not in content:
                content = content.replace(r"\n", "\n").replace(r"\'", "'").replace(r'\"', '"')
            
            files = await _latest_files(self.db, self.project_id)
            prev = files.get(path)
            next_version = (prev.version + 1) if prev else 1
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            if prev is not None and prev.content_hash == content_hash:
                # No-op write: identical content already exists. Reported
                # as success with a `noop` flag so callers/analytics can
                # distinguish "wrote nothing new" from "wrote a change".
                return ToolResult(
                    success=True,
                    output={"path": path, "version": prev.version, "noop": True},
                    execution_time_ms=t["elapsed_ms"],
                )
            row = File(
                project_id=self.project_id,
                path=path,
                content=content,
                content_hash=content_hash,
                version=next_version,
                created_by_task_id=self.created_by_task_id,
            )
            self.db.add(row)
            await self.db.commit()
        return ToolResult(
            success=True,
            output={"path": path, "version": next_version, "noop": False},
            metadata={"content_hash": content_hash},
            execution_time_ms=t["elapsed_ms"],
        )


class FileSearchTool(Tool):
    name = "file_search"
    description = "Find files in the workspace whose path matches a glob pattern, e.g. 'src/**/*.tsx'."
    parameters_schema = {
        "type": "object",
        "properties": {"pattern": {"type": "string"}},
        "required": ["pattern"],
    }

    def __init__(self, db: AsyncSession, project_id: uuid.UUID):
        self.db = db
        self.project_id = project_id

    async def run(self, pattern: str) -> ToolResult:
        with timed() as t:
            files = await _latest_files(self.db, self.project_id)
            matches = sorted(p for p in files if fnmatch.fnmatch(p, pattern))
        return ToolResult(success=True, output={"matches": matches}, execution_time_ms=t["elapsed_ms"])


class DirectoryListerTool(Tool):
    name = "directory_lister"
    description = "List all file paths under a directory prefix (empty string = whole project)."
    parameters_schema = {
        "type": "object",
        "properties": {"prefix": {"type": "string"}},
    }

    def __init__(self, db: AsyncSession, project_id: uuid.UUID):
        self.db = db
        self.project_id = project_id

    async def run(self, prefix: str = "") -> ToolResult:
        with timed() as t:
            files = await _latest_files(self.db, self.project_id)
            matches = sorted(p for p in files if p.startswith(prefix))
        return ToolResult(success=True, output={"paths": matches, "count": len(matches)}, execution_time_ms=t["elapsed_ms"])


class CodeSearchTool(Tool):
    name = "code_search"
    description = "Search file CONTENT across the workspace for a regex pattern; returns matching lines."
    parameters_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "path_glob": {"type": "string", "description": "Optional glob to restrict which files are searched."},
            "max_matches": {"type": "integer"},
        },
        "required": ["pattern"],
    }

    def __init__(self, db: AsyncSession, project_id: uuid.UUID):
        self.db = db
        self.project_id = project_id

    async def run(self, pattern: str, path_glob: str | None = None, max_matches: int = 50) -> ToolResult:
        with timed() as t:
            try:
                regex = re.compile(pattern)
            except re.error as e:
                return ToolResult(success=False, error=f"Invalid regex: {e}", execution_time_ms=0.0)
            files = await _latest_files(self.db, self.project_id)
            results = []
            for path, f in sorted(files.items()):
                if path_glob and not fnmatch.fnmatch(path, path_glob):
                    continue
                for lineno, line in enumerate(f.content.splitlines(), start=1):
                    if regex.search(line):
                        results.append({"path": path, "line": lineno, "text": line.strip()[:300]})
                        if len(results) >= max_matches:
                            break
                if len(results) >= max_matches:
                    break
        return ToolResult(success=True, output={"matches": results}, execution_time_ms=t["elapsed_ms"])


class FileDiffTool(Tool):
    """Fulfils the "git diff" requirement without an actual git repo: the
    `files` table is already versioned, so a unified diff between two
    versions is computed directly with difflib. See
    docs/23-design-decisions.md, "why no git dependency"."""

    name = "file_diff"
    description = "Show a unified diff of a file between two versions (defaults: latest vs. previous)."
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "from_version": {"type": "integer"},
            "to_version": {"type": "integer"},
        },
        "required": ["path"],
    }

    def __init__(self, db: AsyncSession, project_id: uuid.UUID):
        self.db = db
        self.project_id = project_id

    async def run(self, path: str, from_version: int | None = None, to_version: int | None = None) -> ToolResult:
        with timed() as t:
            result = await self.db.execute(
                select(File).where(File.project_id == self.project_id, File.path == path).order_by(File.version)
            )
            versions = list(result.scalars().all())
        if not versions:
            return ToolResult(success=False, error=f"No such file: {path}", execution_time_ms=t["elapsed_ms"])

        to_v = to_version or versions[-1].version
        from_v = from_version if from_version is not None else max(1, to_v - 1)
        by_version = {v.version: v for v in versions}
        old = by_version.get(from_v)
        new = by_version.get(to_v)
        old_lines = old.content.splitlines(keepends=True) if old else []
        new_lines = new.content.splitlines(keepends=True) if new else []
        diff = "".join(
            difflib.unified_diff(old_lines, new_lines, fromfile=f"{path}@v{from_v}", tofile=f"{path}@v{to_v}")
        )
        return ToolResult(success=True, output={"diff": diff, "from_version": from_v, "to_version": to_v}, execution_time_ms=t["elapsed_ms"])


class PackageInspectorTool(Tool):
    name = "package_inspector"
    description = "Read the project's dependency manifests (package.json, requirements.txt, pyproject.toml) if present."
    parameters_schema = {"type": "object", "properties": {}}

    _MANIFESTS = ("package.json", "backend/requirements.txt", "requirements.txt", "pyproject.toml", "backend/pyproject.toml")

    def __init__(self, db: AsyncSession, project_id: uuid.UUID):
        self.db = db
        self.project_id = project_id

    async def run(self) -> ToolResult:
        with timed() as t:
            files = await _latest_files(self.db, self.project_id)
            found = {}
            for name in self._MANIFESTS:
                if name in files:
                    content = files[name].content
                    if name.endswith(".json"):
                        try:
                            data = json.loads(content)
                            found[name] = {
                                "dependencies": list(data.get("dependencies", {}).keys()),
                                "devDependencies": list(data.get("devDependencies", {}).keys()),
                            }
                        except json.JSONDecodeError:
                            found[name] = {"raw": content[:2000]}
                    else:
                        found[name] = {"lines": [l for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]}
        return ToolResult(success=True, output=found, execution_time_ms=t["elapsed_ms"])

class FileTreeTool(Tool):
    name = "file_tree"
    description = "List all file paths. Alias for directory_lister to handle model hallucinations."
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "depth": {"type": "integer"}
        },
    }

    def __init__(self, db: AsyncSession, project_id: uuid.UUID):
        self.db = db
        self.project_id = project_id

    async def run(self, path: str = "", depth: int = 0) -> ToolResult:
        with timed() as t:
            files = await _latest_files(self.db, self.project_id)
            matches = sorted(p for p in files if p.startswith(path))
        return ToolResult(success=True, output={"paths": matches, "count": len(matches)}, execution_time_ms=t["elapsed_ms"])
