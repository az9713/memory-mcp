# Quickstart

Get from zero to a working memory server in about 10 minutes.

---

## Prerequisites

- Python 3.11+
- Claude Code CLI installed and authenticated
- pip available (`python -m pip --version`)

See [installation](installation.md) for full dependency details.

---

## 1. Install dependencies

```bash
pip install mcp sqlite-vec sentence-transformers
```

Expected output (abbreviated):

```
Successfully installed mcp-... sqlite-vec-0.1.9 sentence-transformers-...
```

---

## 2. Register the server with Claude Code

**Project-only** (works only in this directory):

```bash
claude mcp add memory python "C:\Users\simon\Downloads\claude_code_memory_mark_kashef\memory_server.py"
```

**Global** (recommended — available in every project and session):

```bash
claude mcp add --global memory python "C:\Users\simon\Downloads\claude_code_memory_mark_kashef\memory_server.py"
```

Use your full Python path if `python` isn't on PATH:

```bash
claude mcp add --global memory "C:\Users\simon\AppData\Local\Programs\Python\Python313\python.exe" "C:\Users\simon\Downloads\claude_code_memory_mark_kashef\memory_server.py"
```

Verify registration:

```bash
claude mcp list
```

Expected output (among other servers):

```
memory: C:\...\python.exe C:\...\memory_server.py - ✓ Connected
```

---

## 3. Restart Claude Code

The memory server loads at session start. Restart Claude Code to pick up the new registration.

---

## 4. Store your first memory

In a Claude Code session, ask Claude to remember something:

> "Remember that I prefer concise answers with no preamble."

Claude calls `remember` and stores it as a `core` memory. You'll see a confirmation with the memory's ID.

---

## 5. Retrieve it semantically

Ask something related — no exact wording required:

> "What do you know about my communication style?"

Claude calls `recall`, finds the memory by semantic similarity, and quotes it back.

---

## 6. Verify it persists

Start a new Claude Code session and ask the same question. The memory is in `~/.claude/memory.db` and survives restarts.

---

## What just happened

The first time Claude calls a memory tool, the server downloads the `all-MiniLM-L6-v2` embedding model (~80 MB) to `~/.cache/`. Subsequent calls are fast — the model stays loaded in memory for the life of the session.

Every memory gets embedded into a 384-dimensional vector and stored in a SQLite database alongside a `tier`, `importance`, and `last_accessed` timestamp. When you recall, the query is embedded the same way, and results are ranked by semantic similarity × importance × time decay.

---

## Next steps

- [How memory works](../concepts/how-memory-works.md) — understand tiers, decay, and vitality
- [Tool reference](../reference/tools.md) — all parameters for `remember`, `recall`, `forget`, `memories`
- [Configuration](../reference/configuration.md) — change the DB path or decay constants
