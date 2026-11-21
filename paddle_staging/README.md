# Megor Paddle staging

Standalone sandbox service. Production app.py and webhook_app.py are not imported or modified.

Render settings:

- Branch: codex/paddle-staging-20261121
- Root directory: paddle_staging
- Build: pip install -r requirements.txt
- Start: uvicorn staging_app:app --host 0.0.0.0 --port $PORT --no-access-log
- Health: /health

Start with PADDLE_ENABLED=false and PADDLE_ALLOW_LIVE=false. Set staging-only secrets in Render, not Git. Read STAGING.md before enabling payment operations.

The free instance may sleep. This is development hosting, not a reliable live payment endpoint. A durable Supabase inbox retains accepted events; events that do not reach it depend on Paddle retry and reconciliation. The service runs inbox processing only with PADDLE_WORKER_ENABLED=true; reconciliation additionally requires PADDLE_RECONCILE_ENABLED=true, notification.read and a configured initial window.
