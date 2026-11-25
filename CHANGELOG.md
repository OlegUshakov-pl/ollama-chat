# Changelog

## Unreleased

### Added

- **Automatic memory proposals.** A local Ollama model suggests durable facts after chat replies.
  Nothing is written to `USER.md` or `MEMORY.md` until the fact is confirmed on the new `#/memory`
  page. Only text the user typed is analyzed — attachments, web pages, tool results, command output
  and model replies can never become memory facts. Extraction is local-only: memory is never sent
  to a cloud provider.
- New settings block **Auto memory** on `#/settings` with the config keys `autoMemory`,
  `memoryModel`, `memoryEvery`, `memoryMinChars` and `memoryMaxPending` (all off by default).
- New API actions: `getMemoryProposals`, `resolveMemoryProposal`, `resolveAllMemoryProposals`,
  `extractMemory` and `setMemorySettings`; `getSettings` now returns the memory settings too.
- Pending proposals are stored atomically in `<workspace>/memory/pending.json`; accepted changes
  keep `.bak` backups of `MEMORY.md` / `USER.md` and respect `memoryLimit` / `profileLimit`.
- Sidebar **Memory** link with a pending-count badge, a non-blocking notice under replies and a
  Memory page with accept / edit / reject, accept-all / reject-all and manual fact extraction.

### Fixed

- `GET /getSettings` failed with `InvalidOutput` after `SettingsInfo` gained the memory field.
