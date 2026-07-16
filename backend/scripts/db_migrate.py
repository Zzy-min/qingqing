"""Apply versioned schema initialization and verify the resulting version."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

CURRENT_SCHEMA_VERSION = 1


def main() -> int:
    from qingqing_v1.store import create_store

    store = create_store()
    version = store.schema_version()
    if version != CURRENT_SCHEMA_VERSION:
        print(f"schema mismatch: expected={CURRENT_SCHEMA_VERSION} actual={version}")
        return 1
    print(f"schema ready: version={version} backend={type(store).__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
