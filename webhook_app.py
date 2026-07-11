import json
import traceback

from fastapi import FastAPI, HTTPException, Request

from services.webhook_service import (
    InvalidWebhookSignature,
    WebhookConfigurationError,
    WebhookProcessingError,
    get_webhook_summary,
    parse_webhook_payload,
    process_subscription_event,
    verify_webhook_signature,
)


app = FastAPI(
    title="Mango AI Webhook Service",
    version="2.0.0",
)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "Mango AI Webhook",
        "status": "running",
        "version": "2.0.0",
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
        # 必须先验证原始 body，再解析 JSON。
        verify_webhook_signature(
            raw_body=raw_body,
            received_signature=received_signature,
        )

        payload = parse_webhook_payload(
            raw_body
        )

        summary = get_webhook_summary(
            event_name=event_name,
            payload=payload,
        )

        print("=" * 70)
        print("LEMONSQUEEZY WEBHOOK RECEIVED")
        print(
            json.dumps(
                summary,
                indent=2,
                ensure_ascii=False,
            )
        )
        print("=" * 70)

        result = process_subscription_event(
            event_name=event_name,
            payload=payload,
        )

        print("=" * 70)
        print("LEMONSQUEEZY WEBHOOK PROCESSED")
        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )
        print("=" * 70)

        return {
            "ok": True,
            "event": event_name,
            "processed": result.get(
                "processed",
                False,
            ),
            "message": (
                "Webhook processed successfully"
            ),
        }

    except WebhookConfigurationError as exc:
        print(
            f"Webhook configuration error: {exc}"
        )
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                "Webhook service is not configured"
            ),
        ) from exc

    except InvalidWebhookSignature as exc:
        print(
            f"Webhook signature rejected: {exc}"
        )

        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature",
        ) from exc

    except ValueError as exc:
        print(
            f"Webhook payload error: {exc}"
        )

        raise HTTPException(
            status_code=400,
            detail="Invalid webhook payload",
        ) from exc

    except WebhookProcessingError as exc:
        print(
            f"Webhook processing error: {exc}"
        )
        traceback.print_exc()

        # 返回 500，让 LemonSqueezy 后续重试。
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        print(
            f"Unexpected webhook error: {exc}"
        )
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail="Internal webhook error",
        ) from exc