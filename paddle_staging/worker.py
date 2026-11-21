"""Run once per scheduled worker invocation; retries remain in the durable inbox."""
from paddle_routes import backend
if __name__=='__main__':
    results=backend().process_batch()
    print({'processed':sum(r['state']=='done' for r in results),'retry':sum(r['state']=='retry' for r in results)})
