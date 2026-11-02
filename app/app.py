import os
import time
from flask import Flask, jsonify, request, Response
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)
REPLICA = os.getenv('REPLICA_ID', 'local')
REQUESTS = Counter('app_requests_total', 'Completed HTTP requests', ['replica', 'endpoint', 'status'])
DURATION = Histogram('app_request_duration_seconds', 'Request duration', ['replica', 'endpoint'], buckets=(.01,.025,.05,.1,.25,.5,1,2,5))
INFLIGHT = Gauge('app_inflight_requests', 'Active requests', ['replica'])

@app.before_request
def begin():
    if request.path != '/metrics':
        request.environ['start_time'] = time.perf_counter()
        INFLIGHT.labels(REPLICA).inc()

@app.after_request
def finish(response):
    if 'start_time' in request.environ:
        endpoint = request.path if request.path in ('/', '/health', '/work/cpu', '/work/io') else 'other'
        DURATION.labels(REPLICA, endpoint).observe(time.perf_counter() - request.environ['start_time'])
        REQUESTS.labels(REPLICA, endpoint, str(response.status_code)).inc()
        INFLIGHT.labels(REPLICA).dec()
        response.headers['X-Replica-Id'] = REPLICA
    return response

@app.get('/health')
def health():
    return jsonify(status='ok', replica=REPLICA)

@app.get('/')
def index():
    return jsonify(project='Intelligent Load Balancer', replica=REPLICA)

def bounded(name, default, maximum):
    try:
        value = int(request.args.get(name, default))
        if not 0 <= value <= maximum:
            raise ValueError()
        return value
    except ValueError:
        return None

@app.get('/work/cpu')
def cpu():
    iterations = bounded('iterations', 40000, 1000000)
    if iterations is None:
        return jsonify(error='iterations must be 0..1000000', replica=REPLICA), 400
    value = 0
    for i in range(iterations):
        value = (value + i * i) % 1000000007
    return jsonify(replica=REPLICA, iterations=iterations, checksum=value)

@app.get('/work/io')
def io():
    ms = bounded('ms', 40, 1000)
    if ms is None:
        return jsonify(error='ms must be 0..1000', replica=REPLICA), 400
    time.sleep(ms / 1000)
    return jsonify(replica=REPLICA, slept_ms=ms)

@app.get('/metrics')
def metrics():
    return Response(generate_latest(), content_type=CONTENT_TYPE_LATEST)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, threaded=True)
