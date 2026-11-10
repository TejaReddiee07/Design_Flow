"""Block until MongoDB accepts connections (max ~60s)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402

for attempt in range(30):
    try:
        if settings.mongo_uri.startswith("mongomock"):
            print("database is in-memory (mongomock); ready")
            sys.exit(0)
        from pymongo import MongoClient

        client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=4000, appname="designflow-wait")
        client.admin.command("ping")
        client.close()
        print(f"database is ready ({settings.mongo_db})")
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover
        print(f"database not ready ({exc.__class__.__name__}); retry {attempt + 1}/30")
        time.sleep(2)
print("database never became ready", file=sys.stderr)
sys.exit(1)
