"""Bounded event-stream reconciliation. Requires notification.read permission.
Run with an explicit initial --since, then use a persisted checkpoint. Never
advance the checkpoint if fetching or durable enqueue fails. Does not backfill
beyond Paddle's 90-day event retention.
"""
import argparse
from datetime import datetime,timedelta,timezone
from urllib.parse import parse_qs,urlsplit
from services.paddle_service import normalize,EVENTS

def reconcile(service,since=None,now=None):
    env=service.settings.environment
    end=(now or datetime.now(timezone.utc))-timedelta(minutes=1)
    rows=service.admin.table('paddle_reconciliation').select('completed_through').eq('environment',env).execute().data
    if rows: start=datetime.fromisoformat(rows[0]['completed_through'].replace('Z','+00:00'))-timedelta(minutes=10)
    elif since:start=datetime.fromisoformat(since.replace('Z','+00:00'))
    else:raise ValueError('Initial --since is required')
    if start.tzinfo is None or start<end-timedelta(days=89) or start>=end:
        raise ValueError('Reconciliation window invalid or outside retained history; manual backfill required')
    params={'from':start.isoformat(),'to':end.isoformat(),'order_by':'id[ASC]','per_page':200,'event_type':','.join(sorted(EVENTS))}
    count=0
    for _ in range(1000):
        page=service.request('GET','/events',params=params)
        for raw in page['data']:
            event=normalize(raw,env)
            if event:service.enqueue(event);count+=1
        nxt=page.get('meta',{}).get('pagination',{}).get('next')
        if not nxt:break
        u=urlsplit(nxt)
        if u.scheme!='https' or u.netloc!=urlsplit(service.settings.base).netloc or u.path!='/events':
            raise ValueError('Untrusted pagination URL')
        after=parse_qs(u.query).get('after',[''])[0]
        if not after or after==params.get('after'):raise ValueError('Invalid pagination cursor')
        params['after']=after
    else:raise RuntimeError('Pagination limit reached; checkpoint unchanged')
    service.admin.table('paddle_reconciliation').upsert({'environment':env,'completed_through':end.isoformat()}).execute()
    return count

if __name__=='__main__':
    from paddle_routes import backend
    p=argparse.ArgumentParser();p.add_argument('--since');args=p.parse_args()
    print({'durably_enqueued':reconcile(backend(),args.since)})
