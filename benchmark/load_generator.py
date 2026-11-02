import argparse
import csv
import json
import math
import random
import time
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path
import requests

FIELDS = ['scheduled_time','send_time','completion_time','status','latency_seconds','replica','failure','endpoint']

def rate_at(t, base, pattern):
    if pattern == 'step': return base * (2 if t >= 5 else 1)
    if pattern == 'periodic': return base * (1 + .5 * math.sin(2*math.pi*t/10))
    if pattern == 'burst': return base * (3 if 5 <= t < 8 else 1)
    return base

def schedule(duration, rate, pattern, seed):
    rng = random.Random(seed)
    t = 0.0
    # Nonhomogeneous Poisson thinning with a fixed upper bound.
    ceiling = rate * (3 if pattern == 'burst' else 2 if pattern == 'step' else 1.5 if pattern == 'periodic' else 1)
    while t < duration:
        t += rng.expovariate(ceiling)
        if t < duration and rng.random() < rate_at(t, rate, pattern)/ceiling:
            yield t

def run(url, duration, rate, pattern, mix, seed, output, max_pending=200):
    if duration <= 0 or rate <= 0 or max_pending <= 0: raise ValueError('duration, rate, max_pending must be positive')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    arrivals = list(schedule(duration, rate, pattern, seed))
    rng = random.Random(seed + 1)
    origin = time.time()
    rows = []
    pending = set()
    def send(scheduled, endpoint):
        start = time.time()
        try:
            response = requests.get(url.rstrip('/') + endpoint, timeout=5)
            return [scheduled, start, time.time(), response.status_code, time.time()-start, response.headers.get('X-Replica-Id',''), '', endpoint]
        except requests.RequestException as exc:
            return [scheduled, start, time.time(), '', time.time()-start, '', type(exc).__name__, endpoint]
    with ThreadPoolExecutor(max_workers=min(max_pending, 100)) as pool:
        for offset in arrivals:
            delay = origin + offset - time.time()
            if delay > 0: time.sleep(delay)
            endpoint = '/work/cpu' if mix == 'cpu' or rng.random() < .5 else '/work/io'
            completed = {f for f in pending if f.done()}
            for future in completed: rows.append(future.result())
            pending -= completed
            if len(pending) >= max_pending:
                rows.append([origin+offset, '', '', '', '', '', 'generator_overload', endpoint])
            else:
                pending.add(pool.submit(send, origin+offset, endpoint))
        for future in pending: rows.append(future.result())
    rows.sort(key=lambda row: row[0])
    with output.open('w', newline='') as file:
        writer = csv.writer(file); writer.writerow(FIELDS); writer.writerows(rows)
    output.with_suffix('.json').write_text(json.dumps({'url':url,'duration':duration,'rate':rate,'pattern':pattern,'mix':mix,'seed':seed,'max_pending':max_pending,'offered':len(arrivals)}, indent=2))
    return rows

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--url',default='http://localhost:8080'); p.add_argument('--duration',type=float,default=15)
    p.add_argument('--rate',type=float,default=10); p.add_argument('--pattern',choices=['constant','step','periodic','burst'],default='constant')
    p.add_argument('--mix',choices=['cpu','mixed'],default='mixed'); p.add_argument('--seed',type=int,default=42)
    p.add_argument('--output',default='results/run.csv'); p.add_argument('--max-pending',type=int,default=200)
    a=p.parse_args(); run(a.url,a.duration,a.rate,a.pattern,a.mix,a.seed,a.output,a.max_pending)
