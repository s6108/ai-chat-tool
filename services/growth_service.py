import hashlib
import hmac
import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, UUID4

from services.webhook_service import get_supabase_admin

router = APIRouter()


class Visit(BaseModel):
    visitor: UUID4
    country: str = Field(max_length=12)
    source: str = Field(max_length=100, pattern=r"^[a-z0-9_.-]+$")
    medium: str = Field(max_length=100, pattern=r"^[a-z0-9_.-]*$")
    campaign: str = Field(max_length=100, pattern=r"^[a-z0-9_.-]*$")
    content: str = Field(max_length=100, pattern=r"^[a-z0-9_.-]*$")


@router.post("/growth/visit", status_code=204)
def record_visit(visit: Visit, authorization: str = Header(default="")):
    expected_hash = os.environ.get("MEGOR_GROWTH_INGEST_SHA256")
    scheme, _, token = authorization.partition(" ")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    if scheme != "Bearer" or not token or not expected_hash or not hmac.compare_digest(token_hash, expected_hash):
        raise HTTPException(status_code=401)
    day = datetime.now(ZoneInfo("America/Edmonton")).date()
    visit_data = visit.model_dump(mode="json")
    if not re.fullmatch(r"[A-Z]{2}", visit.country):
        visit_data["country"] = "unknown"
    get_supabase_admin().table("megor_web_visits").upsert(
        {**visit_data, "visit_day": day.isoformat()},
        on_conflict="visitor,visit_day", ignore_duplicates=True,
    ).execute()


def record_first_payment(event_name, payload, user_id):
    if not os.environ.get("MEGOR_GROWTH_INGEST_SHA256"):
        return
    meta = payload.get("meta") or {}
    attributes = (payload.get("data") or {}).get("attributes") or {}
    if meta.get("test_mode") or attributes.get("test_mode") or not user_id:
        return
    if event_name not in {"subscription_payment_success", "order_created"}:
        return
    if attributes.get("status") != "paid" or (attributes.get("total") or 0) <= 0:
        return
    paid_at = attributes.get("created_at") or datetime.now(timezone.utc).isoformat()
    get_supabase_admin().table("megor_paid_users").upsert(
        {"user_id": user_id, "paid_at": paid_at},
        on_conflict="user_id", ignore_duplicates=True,
    ).execute()
