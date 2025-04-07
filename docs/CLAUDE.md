# File Organization and Imports

When running scripts or tests, use the following pattern for imports:

```python
# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Then import from src
from src.db.vector_db import VectorDB
```

This ensures scripts can access modules regardless of where they're run from.

# Disabled Features

## Google Drive Integration
The Google Drive search functionality has been disabled in this version. The code is still present but commented out in the following locations:

1. Initialization in `src/main.py` (lines ~204-272)
2. Search functionality in `src/services/mcp/claude.py` (lines ~283-299)
3. Document fetch in `src/services/mcp/claude.py` (lines ~344-353)

To re-enable, uncomment these sections and set `MCP_GDRIVE_ENABLED=true` in the `.env` file.