# Installation

Full dependency details and registration options.

---

## System requirements

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| Python | 3.11 | 3.13 tested and recommended |
| Disk (model cache) | ~80 MB | Downloaded once to `~/.cache/huggingface/` |
| Disk (database) | ~1 MB base | Grows ~1 KB per memory stored |
| RAM | ~300 MB | Model stays loaded for the session |
| OS | Windows, macOS, Linux | sqlite-vec ships pre-compiled wheels for all three |

---

## Python dependencies

```bash
pip install mcp sqlite-vec sentence-transformers
```

| Package | Purpose | Size |
|---------|---------|------|
| `mcp` | Anthropic's MCP SDK — server protocol and FastMCP decorator | Small |
| `sqlite-vec` | SQLite extension for vector similarity search | ~292 KB wheel |
| `sentence-transformers` | Loads and runs `all-MiniLM-L6-v2` for embeddings | Pulls PyTorch |

> **Note:** `sentence-transformers` pulls PyTorch as a dependency (~1 GB). If you're on a machine where disk space is tight, consider using CPU-only PyTorch first: `pip install torch --index-url https://download.pytorch.org/whl/cpu` before installing `sentence-transformers`.

---

## Embedding model download

The model (`all-MiniLM-L6-v2`, ~80 MB) downloads automatically on the first call to `remember` or `recall`. It's cached at:

- **Windows:** `C:\Users\<you>\.cache\huggingface\hub\`
- **macOS/Linux:** `~/.cache/huggingface/hub/`

Subsequent sessions load it from cache in under 2 seconds.

---

## Server registration

### Global registration (recommended)

Available in every Claude Code session regardless of working directory:

```bash
claude mcp add --global memory python "/full/path/to/memory_server.py"
```

Stored in `~/.claude.json` under the global `mcpServers` key.

### Project registration

Available only when Claude Code is opened in a specific directory:

```bash
claude mcp add memory python "/full/path/to/memory_server.py"
```

Stored in `~/.claude.json` under the project-scoped `mcpServers` key for the current directory.

### Switch from project to global

```bash
claude mcp remove memory
claude mcp add --global memory python "/full/path/to/memory_server.py"
```

### Verify registration

```bash
claude mcp list
```

The `memory` server should show `✓ Connected` after the next Claude Code restart.

---

## Database location

The database is created automatically at `~/.claude/memory.db` on first use. No setup required.

To use a different path, edit `DB_PATH` in `memory_server.py`:

```python
DB_PATH = os.path.expanduser("~/.claude/memory.db")  # change this line
```

See [configuration](../reference/configuration.md) for all tunable constants.
