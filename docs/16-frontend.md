# 16 - Frontend

## Design system: "Daedalus"

Deliberately not a generic SaaS admin-dashboard theme. The product is about watching
autonomous agents work, so the visual language borrows from control-room / instrument-
panel aesthetics rather than a friendly marketing dashboard:

- **Palette**: near-black cool graphite base (`#0A0D12`), not pure black or navy. Two
  distinct accent roles rather than one: brass/amber (`#E8A33D`) for primary actions and
  the signature color, cyan (`#3DDBD9`) specifically for "live/running" signals - so the
  two never compete for the same meaning. A full status palette (success/failure/blocked/
  pending) separate from both accents.
- **Type**: three deliberately-chosen families, not a single default. Space Grotesk for
  display/headings (the biggest numbers on the page get some character), IBM Plex Sans for
  UI text, IBM Plex Mono for anything data-shaped (task IDs, token counts, file paths,
  timestamps) - Plex Sans and Plex Mono are the same type family, designed to pair.
- **Signature element**: the task graph uses orthogonal ("step") edges rather than smooth
  bezier curves, reading closer to a circuit/schematic diagram than a generic flowchart
  library default, with task nodes carrying a status-colored left border that glows for
  `running`/`failed`/`needs_approval` states.

Full token definitions: `frontend/tailwind.config.ts`.

## State management

Two deliberately different tools for two different kinds of state:

- **TanStack Query** for everything that comes from the API (projects, tasks, metrics,
  files, approvals) - each hook in `src/api/hooks.ts` owns its own cache key and a
  `refetchInterval` sized to how fast that data actually changes (task lists poll faster
  than metrics; metrics poll faster than a project's own top-level record).
- **Zustand**, one small store, for auth only (`src/store/authStore.ts`). There's no
  argument for a global client-state library here beyond that.

## Live updates: SSE, not the native `EventSource`

The backend stream is genuine Server-Sent Events, but `useProjectEvents`
(`src/hooks/useProjectEvents.ts`) reads it via `fetch` + a `ReadableStream` reader instead
of the browser's built-in `EventSource` API, for one specific reason: `EventSource` cannot
send custom headers, and this API requires a bearer token on every request. Parsing
`data: ` lines out of the stream by hand is a small amount of code in exchange for keeping
authentication consistent across every endpoint, REST or streaming.

## The three-panel workspace

`ProjectWorkspacePage` matches the project brief's layout: a left task list, a center
tabbed view (task graph / live activity / files), and a right panel that shows either
pending approvals (when any exist) or the selected task's detail - tokens used, cost,
files modified, latest error. No hidden chain-of-thought is ever rendered: the right panel
shows `AgentRun.decision_summary` and `output_summary` (both explicitly capped, human-
readable strings the backend produces), never raw model reasoning.

## What was not verified

This repository was built in a sandbox with no network access and no installable npm
packages - `npm install`, `npm run build` (TypeScript compilation), and `npm run test`
(Vitest) were never executed against this code. Every `.tsx`/`.ts` file was checked for
brace/paren balance and for every import (`@/...` and relative) resolving to a real
exported name via a small custom script, and the logic in files without JSX (`layout.ts`,
the API client, the utils) was hand-traced against representative inputs - but this is not
a substitute for an actual `tsc` pass. Running `npm install && npm run build` is the first
thing to do with this frontend in a real environment; see
[20-local-development.md](20-local-development.md).
