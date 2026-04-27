from __future__ import annotations

import os

import uvicorn

from apps.intel_hub.api.app import create_app
from apps.intel_hub.config_loader import resolve_runtime_config_path


def main() -> None:
    host = os.environ.get("INTEL_HUB_HOST", "0.0.0.0")
    port = int(os.environ.get("INTEL_HUB_PORT", "8000"))
    runtime_config_path = resolve_runtime_config_path()
    app = create_app(runtime_config_path)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
