-- Candidate migration. Apply to a staging Supabase project first.
-- Separate records preserve existing Lemon Squeezy/StoreKit entitlements.
BEGIN;
CREATE TABLE public.paddle_customers (
 environment text NOT NULL CHECK(environment IN ('sandbox','live')),
 customer_id text NOT NULL, user_id uuid NOT NULL REFERENCES auth.users(id),
 PRIMARY KEY(environment,customer_id), UNIQUE(environment,user_id)
);
CREATE TABLE public.paddle_prices (
 environment text NOT NULL CHECK(environment IN ('sandbox','live')),
 price_id text NOT NULL, plan text NOT NULL CHECK(plan IN ('premium','pass_30_day')),
 PRIMARY KEY(environment,price_id)
);
INSERT INTO public.paddle_prices VALUES
 ('sandbox','pri_01m7xea1gjs7ry9spdsbaxe5p6','premium'),
 ('sandbox','pri_01m7xea1qw13fh7jp0snvrf006','pass_30_day');
CREATE TABLE public.paddle_inbox (
 environment text NOT NULL CHECK(environment IN ('sandbox','live')), event_id text NOT NULL,
 body jsonb NOT NULL, state text NOT NULL DEFAULT 'pending', attempts int NOT NULL DEFAULT 0,
 available_at timestamptz NOT NULL DEFAULT now(), received_at timestamptz NOT NULL DEFAULT now(),
 last_error text, PRIMARY KEY(environment,event_id), CHECK(state IN ('pending','done','dead'))
);
CREATE INDEX paddle_inbox_pending ON public.paddle_inbox(available_at) WHERE state='pending';
CREATE TABLE public.paddle_subscriptions (
 environment text NOT NULL, id text NOT NULL, customer_id text NOT NULL,
 status text NOT NULL, last_event_at timestamptz NOT NULL, cutoff timestamptz,
 PRIMARY KEY(environment,id), FOREIGN KEY(environment,customer_id) REFERENCES public.paddle_customers
);
CREATE TABLE public.paddle_payments (
 environment text NOT NULL, id text NOT NULL, customer_id text NOT NULL,
 subscription_id text, plan text NOT NULL, paid_at timestamptz NOT NULL,
 period_start timestamptz, period_end timestamptz,
 PRIMARY KEY(environment,id), FOREIGN KEY(environment,customer_id) REFERENCES public.paddle_customers,
 CHECK(plan IN ('premium','pass_30_day')),
 CHECK(plan!='premium' OR (subscription_id IS NOT NULL AND period_end>period_start))
);
CREATE TABLE public.paddle_adjustments (
 environment text NOT NULL, id text NOT NULL, transaction_id text NOT NULL,
 action text NOT NULL, status text NOT NULL, partial boolean NOT NULL,
 last_event_at timestamptz NOT NULL, PRIMARY KEY(environment,id)
);
CREATE TABLE public.paddle_reconciliation (
 environment text PRIMARY KEY CHECK(environment IN ('sandbox','live')),
 completed_through timestamptz NOT NULL
);
-- All access is via a server-side service role, never anon or authenticated clients.
ALTER TABLE public.paddle_customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.paddle_prices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.paddle_inbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.paddle_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.paddle_payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.paddle_adjustments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.paddle_reconciliation ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.paddle_customers,public.paddle_prices,public.paddle_inbox,
 public.paddle_subscriptions,public.paddle_payments,public.paddle_adjustments,
 public.paddle_reconciliation FROM anon,authenticated;
GRANT ALL ON public.paddle_customers,public.paddle_prices,public.paddle_inbox,
 public.paddle_subscriptions,public.paddle_payments,public.paddle_adjustments,
 public.paddle_reconciliation TO service_role;

CREATE FUNCTION public.paddle_bind_customer(p_env text,p_user uuid,p_customer text)
RETURNS text LANGUAGE plpgsql SET search_path=public AS $$
DECLARE existing text;
BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended(p_env||p_user::text,0));
 SELECT customer_id INTO existing FROM paddle_customers WHERE environment=p_env AND user_id=p_user;
 IF existing IS NOT NULL THEN RETURN existing; END IF;
 INSERT INTO paddle_customers VALUES(p_env,p_customer,p_user);
 RETURN p_customer;
END $$;

CREATE FUNCTION public.paddle_enqueue(p_env text,p_event jsonb)
RETURNS void LANGUAGE sql SET search_path=public AS $$
 INSERT INTO paddle_inbox(environment,event_id,body)
 VALUES(p_env,p_event->>'event_id',p_event) ON CONFLICT DO NOTHING;
$$;

CREATE FUNCTION public.paddle_process_next(p_env text)
RETURNS jsonb LANGUAGE plpgsql SET search_path=public AS $$
DECLARE e paddle_inbox; d jsonb; kind text; t timestamptz; plan_name text; customer text;
BEGIN
 SELECT * INTO e FROM paddle_inbox WHERE environment=p_env AND state='pending'
 AND available_at<=now() ORDER BY received_at,event_id FOR UPDATE SKIP LOCKED LIMIT 1;
 IF NOT FOUND THEN RETURN jsonb_build_object('state','idle'); END IF;
 BEGIN
 d=e.body->'data';kind=e.body->>'event_type';t=(e.body->>'occurred_at')::timestamptz;
 customer=d->>'customer_id';
 IF kind LIKE 'subscription.%' OR kind='transaction.completed' THEN
  IF NOT EXISTS(SELECT 1 FROM paddle_customers WHERE environment=p_env AND customer_id=customer)
  THEN RAISE EXCEPTION 'unmapped customer'; END IF;
 END IF;
 IF kind LIKE 'subscription.%' THEN
  IF d->>'status' NOT IN ('active','trialing','past_due','paused','canceled') THEN RAISE EXCEPTION 'invalid status'; END IF;
  IF EXISTS(SELECT 1 FROM paddle_subscriptions WHERE environment=p_env AND id=d->>'id' AND customer_id!=customer)
  THEN RAISE EXCEPTION 'ownership mismatch'; END IF;
  INSERT INTO paddle_subscriptions VALUES(p_env,d->>'id',customer,d->>'status',t,
   CASE WHEN d->'scheduled_change'->>'action' IN ('cancel','pause') THEN (d->'scheduled_change'->>'effective_at')::timestamptz END)
  ON CONFLICT(environment,id) DO UPDATE SET status=excluded.status,last_event_at=excluded.last_event_at,cutoff=excluded.cutoff
  WHERE excluded.last_event_at>paddle_subscriptions.last_event_at;
 ELSIF kind='transaction.completed' THEN
  IF d->>'status'!='completed' OR jsonb_array_length(d->'items')!=1 OR (d->'items'->0->>'quantity')::int!=1
  THEN RAISE EXCEPTION 'unsupported transaction'; END IF;
  SELECT plan INTO plan_name FROM paddle_prices WHERE environment=p_env AND price_id=d->'items'->0->'price'->>'id';
  IF plan_name IS NULL THEN RAISE EXCEPTION 'unknown price'; END IF;
  IF plan_name='pass_30_day' AND d->>'subscription_id' IS NOT NULL THEN RAISE EXCEPTION 'invalid pass'; END IF;
  INSERT INTO paddle_payments VALUES(p_env,d->>'id',customer,d->>'subscription_id',plan_name,t,
   (d->'billing_period'->>'starts_at')::timestamptz,(d->'billing_period'->>'ends_at')::timestamptz)
  ON CONFLICT DO NOTHING;
 ELSIF kind IN ('adjustment.created','adjustment.updated') THEN
  INSERT INTO paddle_adjustments VALUES(p_env,d->>'id',d->>'transaction_id',d->>'action',d->>'status',
   COALESCE(d->>'type','partial')!='full',t)
  ON CONFLICT(environment,id) DO UPDATE SET action=excluded.action,status=excluded.status,
   partial=excluded.partial,last_event_at=excluded.last_event_at
  WHERE excluded.last_event_at>paddle_adjustments.last_event_at;
 END IF;
 UPDATE paddle_inbox SET state='done',last_error=NULL WHERE environment=p_env AND event_id=e.event_id;
 RETURN jsonb_build_object('state','done','event_id',e.event_id);
 EXCEPTION WHEN OTHERS THEN
  -- Keep the event for inspection/replay; never ACK then discard a processing failure.
  UPDATE paddle_inbox SET attempts=attempts+1,state=CASE WHEN attempts+1>=10 THEN 'dead' ELSE 'pending' END,
   available_at=now()+interval '1 minute',last_error='processing failed: inspect restricted inbox'
  WHERE environment=p_env AND event_id=e.event_id;
  RETURN jsonb_build_object('state','retry','event_id',e.event_id);
 END;
END $$;

CREATE FUNCTION public.paddle_access(p_env text,p_user uuid,p_at timestamptz DEFAULT now())
RETURNS jsonb LANGUAGE plpgsql SET search_path=public AS $$
DECLARE premium_end timestamptz; pass_end timestamptz; row record; expiry timestamptz;
BEGIN
 SELECT max(least(p.period_end,coalesce(s.cutoff,p.period_end))) INTO premium_end
 FROM paddle_payments p JOIN paddle_customers c USING(environment,customer_id)
 JOIN paddle_subscriptions s ON s.environment=p.environment AND s.id=p.subscription_id AND s.customer_id=p.customer_id
 WHERE p.environment=p_env AND c.user_id=p_user AND p.plan='premium' AND p.paid_at<=p_at
 AND s.status IN ('active','past_due') AND NOT EXISTS(SELECT 1 FROM paddle_adjustments a
 WHERE a.environment=p.environment AND a.transaction_id=p.id AND a.status='approved' AND a.action IN ('refund','chargeback'));
 FOR row IN SELECT p.* FROM paddle_payments p JOIN paddle_customers c USING(environment,customer_id)
 WHERE p.environment=p_env AND c.user_id=p_user AND p.plan='pass_30_day' AND p.paid_at<=p_at
 AND NOT EXISTS(SELECT 1 FROM paddle_adjustments a WHERE a.environment=p.environment AND a.transaction_id=p.id
 AND a.status='approved' AND a.action IN ('refund','chargeback')) ORDER BY p.paid_at,p.id LOOP
 pass_end=greatest(pass_end,row.paid_at)+interval '30 days';
 END LOOP;
 expiry=greatest(premium_end,pass_end);
 RETURN jsonb_build_object('active',coalesce(expiry>p_at,false),'expires_at',expiry,
 'subscription_expires_at',premium_end,'pass_expires_at',pass_end);
END $$;
REVOKE ALL ON FUNCTION public.paddle_bind_customer(text,uuid,text),public.paddle_enqueue(text,jsonb),
 public.paddle_process_next(text),public.paddle_access(text,uuid,timestamptz) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.paddle_bind_customer(text,uuid,text),public.paddle_enqueue(text,jsonb),
 public.paddle_process_next(text),public.paddle_access(text,uuid,timestamptz) TO service_role;
COMMIT;
