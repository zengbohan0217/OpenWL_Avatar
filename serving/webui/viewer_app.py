"""Local UE Viewer launcher."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn

from serving.api.app import create_app
from serving.ue.config import VIEWER_HOST, VIEWER_PORT


def main() -> None:
    uvicorn.run(create_app(), host=VIEWER_HOST, port=VIEWER_PORT)


if __name__ == "__main__":
    main()
