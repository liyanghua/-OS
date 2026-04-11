 set -a && source .env && set +a && source .venv/bin/activate && uvicorn apps.intel_hub.api.app:create_app --factory --host 0.0.0.0 --port 8000 --reload 2>&1
