import os
import redis
from rq import Worker, Queue

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Standard synchronous Redis connection for RQ
conn = redis.from_url(REDIS_URL)

# Expose default queue
queue = Queue("default", connection=conn)

def run_worker():
    """Start an RQ worker process listening to the 'default' queue."""
    print(f"Starting RQ Worker connected to {REDIS_URL}...")
    worker = Worker([queue], connection=conn)
    worker.work()

if __name__ == "__main__":
    run_worker()
