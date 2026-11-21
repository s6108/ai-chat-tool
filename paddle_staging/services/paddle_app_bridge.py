"""Streamlit server-side helpers. Invoke checkout/portal ONLY on a user button click.
Never serialize the Supabase access token into HTML, a query string, or a log.
"""
import os
from urllib.parse import urlsplit
import requests

def session_action(supabase,user,action,plan=None):
    base=os.environ['PADDLE_BACKEND_URL'].rstrip('/')
    u=urlsplit(base)
    if u.scheme!='https' or not u.hostname or u.username or u.query or u.fragment:
        raise RuntimeError('Configure HTTPS payment backend')
    session=supabase.auth.get_session()
    if not session:raise PermissionError('Sign in again')
    verified=supabase.auth.get_user(session.access_token).user
    if not verified or str(verified.id)!=str(user.id):raise PermissionError('Session does not match user')
    if action not in ('checkout','portal'):raise ValueError('Unsupported action')
    response=requests.post(base+'/paddle/'+action,json={'plan':plan} if action=='checkout' else None,
      headers={'Authorization':'Bearer '+session.access_token},timeout=(3,20),allow_redirects=False)
    response.raise_for_status()
    if 300<=response.status_code<400:raise RuntimeError('Backend redirect rejected')
    data=response.json()
    return data['checkout_url'] if action=='checkout' else data['portal_url']

def overlay_account(admin,user,legacy,strict=False):
    """Preserve independently valid LS access; attach Paddle state separately."""
    if os.getenv('PADDLE_MEMBERSHIP_ENABLED')!='true':return legacy
    env=os.getenv('PADDLE_ENV','sandbox')
    if env not in ('sandbox','live'):raise RuntimeError('Invalid environment')
    try:
        state=admin.rpc('paddle_access',{'p_env':env,'p_user':str(user.id)}).execute().data
    except Exception:
        if strict:raise
        return {**legacy,'paddle_status_unavailable':True}
    result={**legacy,'paddle_active':bool(state.get('active')),'paddle_expires_at':state.get('expires_at')}
    if state.get('active') and not legacy.get('is_premium'):
        from datetime import datetime
        end=state['expires_at']
        result.update(is_premium=True,plan='premium',status='active',access_type='paddle',
          period_end_raw=end,period_end_display=datetime.fromisoformat(end.replace('Z','+00:00')).strftime('%Y-%m-%d'),
          customer_id=None,subscription_id=None,pass_id=None,is_subscription_premium=False,is_pass_premium=False)
    return result
