set -a && source .env && set +a && source .venv/bin/activate && uvicorn apps.intel_hub.api.app:create_app \
  --factory \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --reload-exclude 'third_party/MediaCrawler/*' \
  --reload-exclude 'data/*' \
  --reload-exclude 'browser_data/*' \
  --reload-exclude 'data/sessions/*' \
  --reload-exclude 'data/logs/*' \
  2>&1
