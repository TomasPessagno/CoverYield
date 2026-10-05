"""Write the API's OpenAPI schema to a file (used to generate frontend types).

Usage: python -m api.export_openapi web/openapi.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from api.app import app

if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    out.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
