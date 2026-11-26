# Changelog

## Unreleased

### Added

- **Pinned chats.** Right-click a chat (or use its chat menu) to Pin / Unpin it. Pinned chats are
  shown in a separate **PINNED** section above **TASKS**, are not repeated in **CHATS**, and stay
  pinned after a restart. The `pinned` flag is stored in `ollama-chat.json` via the new
  `POST /setConversationPinned` action; conversations in old configs without the field are treated
  as unpinned. The right-click menu also offers Rename, Download .md and Delete, closes on an
  outside click / `Esc` / scroll and is clamped to the window.
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
