"""Standalone staging process. Does not import the production app or its secrets."""
import asyncio
import contextlib
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from paddle_routes import router,checkout_router,backend
from reconcile import reconcile

log=logging.getLogger('paddle_staging')

async def process_loop():
    while True:
        try:await asyncio.to_thread(lambda: backend().process_batch(limit=20))
        except Exception:log.warning('Paddle worker unavailable; durable events retained')
        await asyncio.sleep(5)

async def reconciliation_loop():
    while True:
        try:await asyncio.to_thread(lambda: reconcile(backend(),os.getenv('PADDLE_RECONCILE_SINCE')))
        except Exception:log.warning('Paddle reconciliation incomplete; checkpoint unchanged')
        await asyncio.sleep(300)

@asynccontextmanager
async def lifespan(app):
    tasks=[]
    if os.getenv('PADDLE_ENABLED')=='true':
        if os.getenv('PADDLE_WORKER_ENABLED')=='true':tasks.append(asyncio.create_task(process_loop()))
        if os.getenv('PADDLE_RECONCILE_ENABLED')=='true':tasks.append(asyncio.create_task(reconciliation_loop()))
    yield
    for task in tasks:task.cancel()
    for task in tasks:
        with contextlib.suppress(asyncio.CancelledError):await task

app=FastAPI(title='Megor Paddle Staging',lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
app.include_router(router)
app.include_router(checkout_router)

@app.get('/health')
def health():
    return {'status':'ok','service':'megor-paddle-staging','environment':os.getenv('PADDLE_ENV','sandbox'),
            'payments_enabled':os.getenv('PADDLE_ENABLED')=='true'}
