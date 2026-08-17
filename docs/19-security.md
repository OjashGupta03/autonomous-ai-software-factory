# 19 - Security

This system executes LLM-generated code. That fact governs most of the decisions here
more than any generic security checklist would.

## Authentication & authorization

JWT (`pyjwt`), bcrypt password hashing (`passlib`), one dependency
(`api/deps.py::get_current_user`) gating every non-auth route. Authorization is
ownership-based and simple: a project belongs to exactly one user, and every project-
scoped endpoint checks `project.owner_id == current_user.id`, returning `404` (not `403`)
on mismatch so a caller can't distinguish "not yours" from "doesn't exist." There is no
role/permission system beyond this - deliberately, per the project brief's "do not
over-engineer authentication."

**Known gap**: the frontend keeps its access token in a module-level JS variable, not
`localStorage` - safer against a broad class of XSS-driven token theft, but it also means
a page refresh currently requires re-login. A production deployment would likely want a
refresh-token flow with an httpOnly cookie; not implemented here.

## Generated code execution

Covered in full in [11-code-execution-sandbox.md](11-code-execution-sandbox.md): no
network by default, memory/CPU/process-count limits, dropped capabilities, non-root user,
host-enforced timeout, argv-only commands. The general-purpose shell tool is additionally
allowlisted at the binary level (`app/tools/exec_tools.py::_SHELL_ALLOWLIST`) - there is
no `shell=True` anywhere in this codebase, so there is no shell-metacharacter injection
surface for it.

## Path traversal

`FileWriterTool` and friends write to `path` as given by the agent, keyed into a `files`
table row (project-scoped), not directly onto a shared filesystem - there is no host path
for `path` to traverse into except within `Workspace.materialize()`'s throwaway per-run
directory, which is discarded after each sandbox call.

## Secrets

`.env` (git-ignored) holds `SECRET_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`; `.env.example`
ships with placeholders only. `SECRET_KEY`'s default in `app/core/config.py`
(`"dev-secret-change-me"`) is intentionally an obvious, greppable placeholder - if it ever
shows up in a real deployment's logs or error messages, that's a loud signal rather than a
quiet one.

## Dependency installation

Sandboxed code execution has no network access by default (see
[11-code-execution-sandbox.md](11-code-execution-sandbox.md)), which means agent-installed
packages cannot be silently pulled from arbitrary registries without an operator
deliberately re-enabling sandbox networking. This is a real friction point for a
from-scratch build (dependencies do need to be installed *somewhere*) traded deliberately
against the larger risk of LLM-directed code having unrestricted internet access by
default.

## Honest limitations, not resolved here

- No rate limiting on the API.
- No CSRF protection (a stateless bearer-token API is a smaller CSRF surface than a
  cookie-session one, but this hasn't been formally reviewed).
- No dependency-vulnerability scanning wired into CI (there is no CI config in this
  repository at all - see [22-deployment.md](22-deployment.md)).
- The Docker-based sandbox is a single isolation layer, not a hardened micro-VM - see
  [11-code-execution-sandbox.md](11-code-execution-sandbox.md)'s limitations section.
