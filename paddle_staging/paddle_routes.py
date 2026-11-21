"""Mount this router on the existing FastAPI webhook app after staging checks."""
import os
import json
import re
from pathlib import Path
import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict
from supabase import create_client
from supabase.lib.client_options import ClientOptions
from services.paddle_service import PaddleBackend, Settings

router=APIRouter(prefix='/paddle')
checkout_router=APIRouter()

@checkout_router.get('/checkout',response_class=HTMLResponse)
def checkout_page():
    try:
        cfg=Settings.from_env();cfg.validate()
        token=os.environ['PADDLE_CLIENT_TOKEN']
        prefix='test_' if cfg.environment=='sandbox' else 'live_'
        if not token.startswith(prefix) or not re.fullmatch(r'[A-Za-z0-9_]+',token):raise ValueError('Invalid client token')
        config=json.dumps({'environment':cfg.environment,'clientToken':token}).replace('<','\\u003c')
        html=(Path(__file__).parent/'checkout.html').read_text().replace('__PADDLE_CONFIG__',config)
        return HTMLResponse(html,headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})
    except Exception as exc:raise HTTPException(503,'Checkout not configured') from exc

class CheckoutBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    plan: str

def backend():
    cfg=Settings.from_env()
    cfg.validate()
    return PaddleBackend(cfg,create_client(os.environ['SUPABASE_URL'],os.environ['SUPABASE_SERVICE_KEY'],
      options=ClientOptions(postgrest_client_timeout=3)))

def authenticated(authorization):
    try:
        service=backend();return service,service.authenticated_user(authorization)
    except PermissionError as exc:raise HTTPException(401,'Verified login required') from exc
    except Exception as exc:raise HTTPException(503,'Payment service unavailable') from exc

@router.post('/checkout')
def checkout(body:CheckoutBody,request:Request):
    service,user=authenticated(request.headers.get('Authorization',''))
    try:return service.checkout(user,body.plan)
    except ValueError as exc:raise HTTPException(400,'Invalid plan') from exc
    except Exception as exc:raise HTTPException(503,'Checkout unavailable; retry later') from exc

@router.get('/access')
def access(request:Request):
    service,user=authenticated(request.headers.get('Authorization',''))
    try:return service.access(user)
    except Exception as exc:raise HTTPException(503,'Membership status unavailable') from exc

@router.post('/portal')
def portal(request:Request):
    service,user=authenticated(request.headers.get('Authorization',''))
    try:return service.portal(user)
    except ValueError as exc:raise HTTPException(404,'No payment account') from exc
    except Exception as exc:raise HTTPException(503,'Portal unavailable') from exc

@router.post('/webhook')
async def webhook(request:Request):
    # Streaming limit also covers requests without Content-Length.
    chunks=[];size=0
    async for chunk in request.stream():
        size+=len(chunk)
        if size>2_000_000:raise HTTPException(413,'Payload too large')
        chunks.append(chunk)
    try:
        service=backend()
        return await run_in_threadpool(service.accept,b''.join(chunks),request.headers.get('Paddle-Signature',''))
    except PermissionError as exc:raise HTTPException(401,'Invalid signature') from exc
    except (ValueError,KeyError,TypeError) as exc:raise HTTPException(400,'Invalid event') from exc
    except Exception as exc:raise HTTPException(503,'Event not durably stored; retry') from exc
