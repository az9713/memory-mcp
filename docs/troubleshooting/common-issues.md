# Common issues

---

## The memory server shows "Failed to connect" in `claude mcp list`

**Cause:** Python can't be found, a dependency is missing, or the path to `memory_server.py` is wrong.

**Fix:**

1. Confirm Python works and the deps are installed:

```bash
python -c "import mcp, sqlite_vec, sentence_transformers; print('OK')"
```

If this fails, reinstall:

```bash
pip install mcp sqlite-vec sentence-transformers
```

2. Confirm the path in the registration is correct:

```bash
claude mcp list
```

Look at the command shown for `memory`. If the path is wrong, remove and re-add:

```bash
claude mcp remove memory
claude mcp add --global memory "C:\full\path\to\python.exe" "C:\full\path\to\memory_server.py"
```

3. Test the server manually:

```bash
echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{}},"id":1}' | python memory_server.py
```

It should print a JSON response. If it prints a Python traceback, the error message will tell you what's missing.

---

## `recall` returns nothing even though I stored memories

**Cause:** The query embedding is too far from the stored embeddings, or the database is empty.

**Fix:**

1. Check that memories are actually stored:

```bash
python -c "
import sqlite3
conn = sqlite3.connect('C:/Users/<you>/.claude/memory.db')
rows = conn.execute('SELECT id, tier, content FROM memories').fetchall()
print(f'{len(rows)} memories found')
for r in rows: print(r)
"
```

2. If the database is empty, the server may have connected before any `remember` calls were made. Store something and try again.

3. If memories exist but search still returns nothing, the query may be too short or too generic. Try a more specific query — "TypeScript strict mode preference" instead of "preferences".

4. If you changed `MODEL_NAME` after storing memories, the embedding spaces no longer match. Delete the database and start fresh:

```bash
del "%USERPROFILE%\.claude\memory.db"
```

---

## The first `recall` or `remember` takes 30+ seconds

**Cause:** The `all-MiniLM-L6-v2` model is downloading for the first time (~80 MB).

**Fix:** This is expected on first use. Subsequent calls use the cached model and complete in under 1 second. The cache is at:

- **Windows:** `C:\Users\<you>\.cache\huggingface\hub\`
- **macOS/Linux:** `~/.cache/huggingface/hub/`

If the download keeps failing, check your internet connection or configure a HuggingFace mirror via the `HF_ENDPOINT` environment variable.

---

## Changes to `memory_server.py` aren't taking effect

**Cause:** Claude Code has the old version of the server running in memory.

**Fix:** Restart Claude Code. The server process is spawned fresh on each session start — there's no hot reload.

---

## `memories()` shows a memory I deleted

**Cause:** The deletion succeeded but a stale in-memory list was shown.

**Fix:** Call `memories()` again. The deletion is committed to disk immediately — if it's gone from the second call, it was a display race. If it persists, check the `forget` call returned `{"deleted": true}` — if it returned `{"deleted": false, "error": "memory not found"}`, the ID was already gone.

---

## The server connects but the tools don't appear in Claude Code

**Cause:** Claude Code only loads MCP tools at session start. If the server was registered mid-session, the tools won't appear until restart.

**Fix:** Restart Claude Code. After restart, ask Claude "what memory tools do you have?" and it will confirm `remember`, `recall`, `forget`, and `memories` are available.

---

## `remember` fails with "content cannot be empty"

**Cause:** The content string was empty or only whitespace.

**Fix:** Ensure the content has at least one non-whitespace character. If Claude is generating empty content, check the prompt — Claude may have misunderstood what to store.
