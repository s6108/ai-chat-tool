"""Candidate Paddle backend; disabled by default. No secrets in browser output."""
import hashlib
import hmac
import json
import os
import re
import time
from dataclasses import dataclass
from urllib.parse import urlsplit
import requests

EVENTS = {'transaction.completed', 'transaction.payment_failed', 'subscription.created',
          'subscription.updated', 'subscription.canceled', 'subscription.activated',
          'subscription.paused', 'subscription.resumed', 'subscription.past_due',
          'adjustment.created', 'adjustment.updated'}

@dataclass(frozen=True)
class Settings:
    environment: str
    api_key: str
    webhook_secret: str
    checkout_url: str
    premium_price: str
    pass_price: str
    enabled: bool = False
    allow_live: bool = False

    @classmethod
    def from_env(cls):
        return cls(os.getenv('PADDLE_ENV','sandbox'), os.getenv('PADDLE_API_KEY',''),
          os.getenv('PADDLE_NOTIFICATION_WEBHOOK_SECRET',''), os.getenv('PADDLE_CHECKOUT_URL',''),
          os.getenv('PADDLE_PREMIUM_PRICE_ID',''), os.getenv('PADDLE_PASS_PRICE_ID',''),
          os.getenv('PADDLE_ENABLED')=='true', os.getenv('PADDLE_ALLOW_LIVE')=='true')

    def validate(self):
        if not self.enabled:
            raise RuntimeError('Paddle disabled')
        if self.environment not in ('sandbox','live'):
            raise RuntimeError('Invalid environment')
        if self.environment=='live' and not self.allow_live:
            raise RuntimeError('Live not enabled')
        prefix = 'pdl_sdbx_apikey_' if self.environment=='sandbox' else 'pdl_live_apikey_'
        if not self.api_key.startswith(prefix) or not self.webhook_secret:
            raise RuntimeError('Missing or mismatched Paddle credentials')
        u=urlsplit(self.checkout_url)
        if u.scheme!='https' or not u.hostname or u.username or u.query or u.fragment:
            raise RuntimeError('Invalid checkout URL')
        if not all(re.fullmatch(r'pri_[a-z0-9]{26}',p) for p in (self.premium_price,self.pass_price)):
            raise RuntimeError('Invalid price IDs')
        if self.premium_price==self.pass_price:
            raise RuntimeError('Prices must differ')

    @property
    def base(self):
        return 'https://sandbox-api.paddle.com' if self.environment=='sandbox' else 'https://api.paddle.com'


def verify(raw, header, secret, now=None):
    if not secret or not header:
        return False
    parts={}
    for item in header.split(';'):
        k,sep,v=item.strip().partition('=')
        if sep:parts.setdefault(k,[]).append(v)
    stamps=parts.get('ts',[])
    if len(stamps)!=1:return False
    ts=stamps[0]
    try:
        if abs((time.time() if now is None else now)-int(ts))>300:return False
    except ValueError:return False
    digest=hmac.new(secret.encode(),ts.encode()+b':'+raw,hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(digest,x) for x in parts.get('h1',[]))


def normalize(event, environment):
    """Retain only fulfillment fields, not emails, addresses or payment details."""
    from datetime import datetime
    if not isinstance(event,dict):raise ValueError('Invalid event')
    eid=event.get('event_id','')
    allowed=r'evt_[a-z0-9]{26}' if environment=='live' else r'(?:evt_|ntfsimevt_)[a-z0-9]{26}'
    if not isinstance(eid,str) or not re.fullmatch(allowed,eid):raise ValueError('Invalid event ID')
    kind=event.get('event_type')
    if kind not in EVENTS:return None
    at=event['occurred_at'];dt=datetime.fromisoformat(at.replace('Z','+00:00'))
    if dt.tzinfo is None:raise ValueError('Timezone required')
    data=event['data']
    if not isinstance(data,dict):raise ValueError('Invalid event data')
    keep={k:data.get(k) for k in ('id','customer_id','status')}
    if not isinstance(keep['id'],str):raise ValueError('Missing entity ID')
    if kind.startswith('subscription.'):
        keep['scheduled_change']=data.get('scheduled_change')
    elif kind.startswith('transaction.'):
        keep.update({k:data.get(k) for k in ('subscription_id','billing_period')})
        keep['items']=[{'quantity':i.get('quantity'),'price':{'id':(i.get('price') or {}).get('id')}} for i in data.get('items',[])]
    else:
        keep.update({k:data.get(k) for k in ('transaction_id','action','type')})
    return dict(event_id=eid,event_type=kind,occurred_at=at,data=keep)


class PaddleBackend:
    def __init__(self, settings, admin, http=requests):
        settings.validate()
        self.settings,self.admin,self.http=settings,admin,http

    def request(self,method,path,body=None,params=None):
        if not path.startswith('/') or path.startswith('//'):raise ValueError('Invalid API path')
        response=self.http.request(method,self.settings.base+path,
          headers={'Authorization':'Bearer '+self.settings.api_key,'Paddle-Version':'1'},
          json=body,params=params,timeout=(3,12),allow_redirects=False)
        if response.status_code>=400:
            # Diagnostic metadata only: never log headers, payloads, email or keys.
            import logging
            try:code=response.json().get('error',{}).get('code','unknown')
            except Exception:code='unknown'
            if not isinstance(code,str) or not re.fullmatch(r'[a-z_]{1,80}',code):code='unknown'
            logging.getLogger('paddle_staging').warning('Paddle API operation=%s resource=%s status=%s code=%s',method,path.split('/')[1],response.status_code,code)
        response.raise_for_status()
        if 300<=response.status_code<400:raise RuntimeError('API redirect rejected')
        return response.json()

    def authenticated_user(self, authorization):
        if not authorization.startswith('Bearer '):raise PermissionError('Authentication required')
        try: user=self.admin.auth.get_user(authorization[7:]).user
        except Exception as exc:raise PermissionError('Invalid session') from exc
        if not user or not user.id or not user.email or not user.email_confirmed_at:
            raise PermissionError('Verified account required')
        return user

    def checkout(self,user,plan):
        prices={'premium':self.settings.premium_price,'pass_30_day':self.settings.pass_price}
        if plan not in prices:raise ValueError('Unknown plan')
        configured=self.admin.table('paddle_prices').select('plan').eq('environment',self.settings.environment).eq('price_id',prices[plan]).execute().data
        if not configured or configured[0]['plan']!=plan:raise RuntimeError('Catalog not registered')
        rows=self.admin.table('paddle_customers').select('customer_id').eq('environment',self.settings.environment).eq('user_id',str(user.id)).execute().data
        if rows:customer=rows[0]['customer_id']
        else:
            try: customer=self.request('POST','/customers',{'email':user.email})['data']['id']
            except requests.HTTPError as exc:
                if exc.response is None or exc.response.status_code!=409:raise
                # Verified Supabase email is the only fallback bridge, never browser email.
                found=self.request('GET','/customers',params={'email':user.email})['data']
                if len(found)!=1:raise RuntimeError('Customer needs manual reconciliation')
                customer=found[0]['id']
            customer=self.admin.rpc('paddle_bind_customer',{'p_env':self.settings.environment,'p_user':str(user.id),'p_customer':customer}).execute().data
        transaction=self.request('POST','/transactions',{'customer_id':customer,'collection_mode':'automatic',
          'items':[{'price_id':prices[plan],'quantity':1}], 'checkout':{'url':self.settings.checkout_url}})['data']
        link=transaction.get('checkout',{}).get('url')
        if not link or urlsplit(link)._replace(query='',fragment='').geturl()!=self.settings.checkout_url:
            raise RuntimeError('Unexpected checkout destination')
        return {'checkout_url':link,'transaction_id':transaction['id']}

    def accept(self,raw,signature):
        if not verify(raw,signature,self.settings.webhook_secret):raise PermissionError('Invalid signature')
        event=normalize(json.loads(raw),self.settings.environment)
        if event:self.enqueue(event)
        return {'accepted':True}

    def enqueue(self,event):
        self.admin.rpc('paddle_enqueue',{'p_env':self.settings.environment,'p_event':event}).execute()

    def access(self,user):
        return self.admin.rpc('paddle_access',{'p_env':self.settings.environment,'p_user':str(user.id)}).execute().data

    def portal(self,user):
        rows=self.admin.table('paddle_customers').select('customer_id').eq('environment',self.settings.environment).eq('user_id',str(user.id)).execute().data
        if len(rows)!=1:raise ValueError('No bound customer')
        session=self.request('POST','/customers/'+rows[0]['customer_id']+'/portal-sessions',{})['data']
        link=session['urls']['general']['overview']
        url=urlsplit(link)
        host='sandbox-customer-portal.paddle.com' if self.settings.environment=='sandbox' else 'customer-portal.paddle.com'
        if url.scheme!='https' or url.hostname!=host or url.username:raise RuntimeError('Unexpected portal URL')
        return {'portal_url':link}

    def process_batch(self,limit=100):
        results=[]
        for _ in range(limit):
            result=self.admin.rpc('paddle_process_next',{'p_env':self.settings.environment}).execute().data
            if result['state']=='idle':break
            results.append(result)
        return results
