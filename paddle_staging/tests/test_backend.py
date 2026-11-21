import hashlib,hmac,json,sys,time,unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from services.paddle_service import Settings,PaddleBackend,normalize,verify
from reconcile import reconcile
from datetime import datetime,timezone

CFG=Settings('sandbox','pdl_sdbx_apikey_fixture','fixture-secret','https://checkout.example.com/checkout',
 'pri_01m7xea1gjs7ry9spdsbaxe5p6','pri_01m7xea1qw13fh7jp0snvrf006',True)
def event():return {'event_id':'evt_'+'0'*25+'1','event_type':'transaction.completed','occurred_at':'2026-11-21T00:00:00Z',
 'data':{'id':'txn_fixture','customer_id':'ctm_fixture','status':'completed','items':[{'price':{'id':CFG.pass_price},'quantity':1}],
 'customer':{'email':'private@example.com'},'payments':[{'card':{'last4':'1234'}}],'custom_data':{'userId':'attacker'}}}

class BackendTests(unittest.TestCase):
 def setUp(self):self.admin=MagicMock();self.s=PaddleBackend(CFG,self.admin)
 def test_fail_closed_environment(self):
  for cfg in [replace(CFG,enabled=False),replace(CFG,environment='live'),replace(CFG,api_key='pdl_live_apikey_wrong'),replace(CFG,checkout_url='http://local')]:
   with self.assertRaises(RuntimeError):cfg.validate()
 def test_signature_and_minimal_inbox(self):
  raw=json.dumps(event()).encode();ts=str(int(time.time()));sig=hmac.new(CFG.webhook_secret.encode(),ts.encode()+b':'+raw,hashlib.sha256).hexdigest()
  self.s.accept(raw,f'ts={ts};h1={sig}')
  saved=self.admin.rpc.call_args.args[1]['p_event'];self.assertNotIn('private',json.dumps(saved));self.assertNotIn('payments',saved['data']);self.assertNotIn('custom_data',saved['data'])
  with self.assertRaises(PermissionError):self.s.accept(raw+b' ',f'ts={ts};h1={sig}')
 def test_expiry_and_duplicate_timestamps(self):
  self.assertFalse(verify(b'x','ts=1;h1=x',CFG.webhook_secret,now=1000))
  self.assertFalse(verify(b'x','ts=1;ts=1;h1=x',CFG.webhook_secret,now=1))
 def test_live_rejects_simulator(self):
  e=event();e['event_id']='ntfsimevt_'+'0'*26
  self.assertIsNotNone(normalize(e,'sandbox'))
  with self.assertRaises(ValueError):normalize(e,'live')
 def test_auth_checked_by_supabase(self):
  with self.assertRaises(PermissionError):self.s.authenticated_user('')
  user=N(id='verified',email='fixture@example.com',email_confirmed_at='2026-01-01')
  self.admin.auth.get_user.return_value=N(user=user)
  self.assertEqual(self.s.authenticated_user('Bearer fixture-jwt').id,'verified')
  self.admin.auth.get_user.assert_called_once_with('fixture-jwt')
  user.email_confirmed_at=None
  with self.assertRaises(PermissionError):self.s.authenticated_user('Bearer fixture-jwt')
 def test_browser_cannot_choose_customer_or_price(self):
  with self.assertRaises(ValueError):self.s.checkout(N(id='user'), 'arbitrary_price')
  from paddle_routes import CheckoutBody
  with self.assertRaises(ValueError):CheckoutBody(plan='premium',user_id='other',customer_id='other')
 def test_checkout_uses_trusted_binding(self):
  # Two DB reads: allowlisted price, then trusted customer binding.
  class Query:
   def __init__(self,data):self.data=data
   def __getattr__(self,k):return lambda *a,**kw:self
  self.admin.table.side_effect=[Query([{'plan':'premium'}]),Query([{'customer_id':'ctm_trusted'}])]
  self.s.request=MagicMock(return_value={'data':{'id':'txn_fixture','checkout':{'url':CFG.checkout_url+'?_ptxn=txn_fixture'}}})
  self.s.checkout(N(id='verified-user'), 'premium')
  body=self.s.request.call_args.args[2]
  self.assertEqual(body['customer_id'],'ctm_trusted');self.assertEqual(body['items'],[{'price_id':CFG.premium_price,'quantity':1}]);self.assertNotIn('custom_data',body)
 def test_inbox_storage_failure_is_not_acknowledged(self):
  self.admin.rpc.return_value.execute.side_effect=RuntimeError('db unavailable')
  raw=json.dumps(event()).encode();ts=str(int(time.time()));sig=hmac.new(CFG.webhook_secret.encode(),ts.encode()+b':'+raw,hashlib.sha256).hexdigest()
  with self.assertRaises(RuntimeError):self.s.accept(raw,f'ts={ts};h1={sig}')
 def test_reconciliation_dedup_and_checkpoint(self):
  self.admin.table.return_value.select.return_value.eq.return_value.execute.return_value.data=[]
  self.s.request=MagicMock(return_value={'data':[event()], 'meta':{'pagination':{'next':None}}})
  self.assertEqual(reconcile(self.s,'2026-11-20T00:00:00Z',datetime(2026,11,21,12,tzinfo=timezone.utc)),1)
  self.admin.table.return_value.upsert.assert_called_once()
 def test_reconciliation_failure_keeps_checkpoint(self):
  self.admin.table.return_value.select.return_value.eq.return_value.execute.return_value.data=[]
  self.s.request=MagicMock(side_effect=RuntimeError('network failed'))
  with self.assertRaises(RuntimeError):reconcile(self.s,'2026-11-20T00:00:00Z',datetime(2026,11,21,12,tzinfo=timezone.utc))
  self.admin.table.return_value.upsert.assert_not_called()
 def test_pagination_cannot_leak_credentials(self):
  self.admin.table.return_value.select.return_value.eq.return_value.execute.return_value.data=[]
  self.s.request=MagicMock(return_value={'data':[],'meta':{'pagination':{'next':'https://attacker.example/events?after=x'}}})
  with self.assertRaises(ValueError):reconcile(self.s,'2026-11-20T00:00:00Z',datetime(2026,11,21,12,tzinfo=timezone.utc))
  self.assertEqual(self.s.request.call_count,1)
  self.admin.table.return_value.upsert.assert_not_called()
 def test_portal_cannot_target_another_customer(self):
  class Query:
   data=[{'customer_id':'ctm_owned'}]
   def __getattr__(self,k):return lambda *a,**kw:self
  self.admin.table.return_value=Query()
  self.s.request=MagicMock(return_value={'data':{'urls':{'general':{'overview':'https://sandbox-customer-portal.paddle.com/cpl_fixture?token=fixture'}}}})
  self.assertTrue(self.s.portal(N(id='verified-user'))['portal_url'].startswith('https://sandbox-customer-portal.paddle.com/'))
  self.assertEqual(self.s.request.call_args.args[1],'/customers/ctm_owned/portal-sessions')
 def test_account_overlay_preserves_other_provider(self):
  from services.paddle_app_bridge import overlay_account
  old={'is_premium':True,'subscription_id':'ls_own','plan':'premium'}
  self.admin.rpc.return_value.execute.return_value.data={'active':False,'expires_at':None}
  with patch.dict('os.environ',{'PADDLE_MEMBERSHIP_ENABLED':'true','PADDLE_ENV':'sandbox'}):
   result=overlay_account(self.admin,N(id='user'),old)
   self.assertTrue(result['is_premium']);self.assertEqual(result['subscription_id'],'ls_own')
 def test_session_bridge_rejects_wrong_logged_in_user(self):
  from services.paddle_app_bridge import session_action
  auth=MagicMock();auth.auth.get_session.return_value=N(access_token='fixture-jwt');auth.auth.get_user.return_value=N(user=N(id='other-user'))
  with patch.dict('os.environ',{'PADDLE_BACKEND_URL':'https://backend.example.com'}),patch('services.paddle_app_bridge.requests.post') as post:
   with self.assertRaises(PermissionError):session_action(auth,N(id='expected-user'),'checkout','premium')
   post.assert_not_called()

class RouteTests(unittest.TestCase):
 def setUp(self):
  from fastapi import FastAPI
  from fastapi.testclient import TestClient
  from paddle_routes import router
  app=FastAPI();app.include_router(router);self.client=TestClient(app)
 def test_disabled_backend(self):
  with patch('paddle_routes.backend',side_effect=RuntimeError('disabled')):
   self.assertEqual(self.client.post('/paddle/checkout',json={'plan':'premium'}).status_code,503)
 def test_webhook_failure_returns_retry_status(self):
  s=MagicMock();s.accept.side_effect=RuntimeError('db down')
  with patch('paddle_routes.backend',return_value=s):self.assertEqual(self.client.post('/paddle/webhook',content='{}').status_code,503)
 def test_webhook_success(self):
  s=MagicMock();s.accept.return_value={'accepted':True}
  with patch('paddle_routes.backend',return_value=s):self.assertEqual(self.client.post('/paddle/webhook',content='{}').status_code,200)
if __name__=='__main__':unittest.main(verbosity=2)
