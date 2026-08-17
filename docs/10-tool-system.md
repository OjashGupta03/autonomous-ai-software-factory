# 10 - Tool System

## Structured results, always

Every tool returns `ToolResult(success, output, error, metadata, execution_time_ms)`
(`app/tools/base.py`). Agents never narrate an action without actually taking it - if a
tool isn't called, nothing happened, and the agent's final summary is the only claim it
gets to make.

## Two families, split by whether they execute anything

**DB-backed tools** (`app/tools/db_tools.py`) - `file_reader`, `file_writer`,
`file_search`, `directory_lister`, `code_search`, `file_diff`, `package_inspector`. These
read/write the versioned `files` table directly via the async session. None of them run
generated code, so none of them need the sandbox - reading and writing text is not a
security boundary the way executing it is.

**Sandbox-backed tools** (`app/tools/exec_tools.py`) - `test_runner`, `lint_runner`,
`formatter`, `shell_command_runner`. Every one of these materializes the project's current
files to a throwaway directory (`sandbox.Workspace`) and runs the actual command inside a
locked-down container (`DockerSandboxExecutor`) - see
[11-code-execution-sandbox.md](11-code-execution-sandbox.md).

## Two items from the original tool list, deliberately consolidated

- **"git diff" is not backed by git.** `FileDiffTool` computes a unified diff between two
  *versions* of a file using `difflib`, directly against the already-versioned `files`
  table. There is no git repository in the workspace at all. This is simpler, needs no
  extra dependency, and the version history it diffs against is the same one the rest of
  the system already treats as authoritative.
- **"Documentation retrieval" is not a separate tool.** The only documentation an agent
  can safely read is whatever already exists in the project workspace (a README, a docs/
  file another task wrote) - sandboxed code execution has no outbound network access by
  default (`SANDBOX_NETWORK_DISABLED=true`), so there is nothing external to "retrieve".
  `file_search` + `file_reader` cover this without a redundant tool.

## The shell tool is an allowlist, not a shell

`ShellCommandRunnerTool` takes `argv: list[str]`, never a raw shell string, and the first
element must be on a fixed allowlist (`ls`, `cat`, `pytest`, `npm`, `black`, `ruff`, ...
- see `app/tools/exec_tools.py::_SHELL_ALLOWLIST`). There is no `shell=True` path
anywhere in this codebase, so there is no shell-metacharacter injection surface for this
tool to have.

## A real bug this design surfaced

`Tool.run()` implementations time themselves with a small `with timed() as t:` context
manager. Several tools return early *inside* that block (e.g. `file_writer`'s no-op path
when the content is identical to the latest version). The first implementation of `timed()`
only computed elapsed time in a `finally` clause, which meant reading `t["elapsed_ms"]` as
part of an early return's own return value ran *before* that `finally` fired - a `KeyError`
on every such path. The fix (`_Timer`, a small class computing elapsed time live via a
property on every access) and a standalone reproduction confirming it are in
`app/tools/base.py`. Documented here because it's a good example of exactly the kind of
bug that only shows up when the code actually runs, which is why this repository's build
process included running what could be run rather than only reading the code back.
