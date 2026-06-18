from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.local_dry_run import run_local_dry_run
from tools.serialization import to_plain_data

if __name__ == "__main__":
    print(json.dumps(to_plain_data(run_local_dry_run()), ensure_ascii=False, indent=2))
