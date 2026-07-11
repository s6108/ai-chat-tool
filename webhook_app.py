import json

from fastapi import FastAPI, HTTPException, Request

from services.webhook_service import (
    InvalidWebhookSignature,
    WebhookConfigurationError,
    get_webhook_summary,
    parse_webhook_payload,
    verify_webhook_signature,
)


app = FastAPI(
    title="Mango AI Webhook Service",
    version="1.0.0",
)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "Mango AI Webhook",
        "status": "running",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook")
async def lemon_squeezy_webhook(
    request: Request,
) -> dict[str, object]:
    raw_body = await request.body()

    received_signature = request.headers.get(
        "X-Signature",
        "",
    )
    event_name = request.headers.get(
        "X-Event-Name",
        "unknown",
    )

    try:
        verify_webhook_signature(
            raw_body=raw_body,
            received_signature=received_signature,
        )

        payload = parse_webhook_payload(raw_body)

    except WebhookConfigurationError as exc:
        print(f"Webhook configuration error: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Webhook service is not configured",
        ) from exc

    except InvalidWebhookSignature as exc:
        print(f"Webhook signature rejected: {exc}")
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature",
        ) from exc

    except ValueError as exc:
        print(f"Webhook payload error: {exc}")
        raise HTTPException(
            status_code=400,
            detail="Invalid webhook payload",
        ) from exc

    summary = get_webhook_summary(
        event_name=event_name,
        payload=payload,
    )

    print("=" * 60)
    print("LEMONSQUEEZY WEBHOOK RECEIVED")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("=" * 60)

    # Phase 1：暂时只验证并打印，不修改 Supabase。
    return {
        "ok": True,
        "event": event_name,
        "message": "Webhook received successfully",
    }