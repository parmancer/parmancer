# Development Tools

## README/Docstring Synchronization

### `sync_readme.py`

Syncs README.md with the module docstring from `parmancer/__init__.py`.

**Usage:**
```bash
# Check synchronization
tox -e check-readme-sync

# Update README.md from module docstring (default)
python tools/sync_readme.py
```
