import json
import logging
import math
import os
import socket
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
import requests
from controller.forecasting import ewma, persistence, evaluate
from controller.scoring import preferences, shares, bounded_weights

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
LOG = logging.getLogger(__name__)
NAMES = ('app1', 'app2', 'app3')
CAPACITIES = dict(zip(NAMES, (0.5, 1.0, 1.5)))  # configured Compose CPU limits
POLICY = os.getenv('POLICY', 'reactive')
INTERVAL = float(os.getenv('CONTROLLER_INTERVAL', '2'))
PROM = os.getenv('PROMETHEUS_URL', 'http://prometheus:9090')
SOCKET = os.getenv('HAPROXY_SOCKET', '/run/haproxy/admin.sock')
FORECAST = os.getenv('FORECAST', 'ewma')
SLO = float(os.getenv('LATENCY_SLO', '.5'))
STATUS = {'policy': POLICY, 'weights': ({'app1': 50, 'app2': 100, 'app3': 150} if POLICY != 'round_robin' else {k: 100 for k in NAMES}), 'mode': 'starting', 'prediction_enabled': False, 'forecast_method': FORECAST}

def query(expression, now=None, max_age=15):
    response = requests.get(PROM + '/api/v1/query', params={'query': expression}, timeout=2)
    response.raise_for_status()
    data = response.json()
    if data.get('status') != 'success':
        raise ValueError('Prometheus query failed')
    result = {}
    for item in data['data']['result']:
        stamp, raw = item['value']
        value = float(raw)
        if math.isfinite(value) and (now or time.time()) - float(stamp) <= max_age:
            result[item['metric'].get('instance', '')] = value
    return result

def collect():
    now = time.time()
    expressions = {
        'health': 'up{job="backends"}',
        'cpu': 'rate(process_cpu_seconds_total{job="backends"}[30s])',
        'memory': 'process_resident_memory_bytes{job="backends"}',
        'inflight': 'app_inflight_requests{job="backends"}',
        'latency': 'sum by(instance)(rate(app_request_duration_seconds_sum{job="backends"}[30s])) / sum by(instance)(rate(app_request_duration_seconds_count{job="backends"}[30s]))',
        'rate': 'sum by(instance)(rate(app_requests_total{job="backends"}[10s]))',
    }
    metrics = {key: query(expr, now) for key,expr in expressions.items()}
    if not metrics['health']:
        raise ValueError('backend health telemetry unavailable or stale')
    samples = {}
    for name in NAMES:
        instance = name + ':8000'
        samples[name] = {k: metrics[k].get(instance) for k in ('cpu','memory','inflight','latency','rate')}
        samples[name]['healthy'] = metrics['health'].get(instance) == 1
    return samples

def runtime(command):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(2)
        sock.connect(SOCKET)
        sock.sendall((command + '\n').encode())
        chunks = []
        while True:
            part = sock.recv(4096)
            if not part:
                break
            chunks.append(part)
    answer = b''.join(chunks).decode(errors='replace')
    if answer.lstrip().lower().startswith(('error:', 'unknown command', 'no such server')):
        raise RuntimeError(answer)
    return answer

def apply_weights(weights):
    for name, weight in weights.items():
        runtime(f'set server servers/{name} weight {weight}')

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/status':
            self.send_error(404)
            return
        payload = json.dumps(STATUS).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

def serve_status():
    HTTPServer(('0.0.0.0', 8081), Handler).serve_forever()

def cycle(samples, history, previous):
    if not all(s['healthy'] and any(s.get(k) is not None for k in ('cpu','memory','inflight','latency')) for s in samples.values()):
        # A backend down is excluded; missing telemetry on an otherwise healthy node triggers static fallback.
        if any(s['healthy'] and all(s.get(k) is None for k in ('cpu','memory','inflight','latency')) for s in samples.values()):
            pref = {k: CAPACITIES[k] if samples[k]['healthy'] else 0 for k in NAMES}
            mode = 'static_fallback'
        else:
            pref = preferences(samples, CAPACITIES, latency_slo=SLO)
            mode = 'reactive'
    else:
        pref = preferences(samples, CAPACITIES, latency_slo=SLO)
        mode = 'reactive'
    predicted = None
    horizon = max(1, round(10/INTERVAL))
    if POLICY == 'predictive' and len(history) >= horizon+3 and mode == 'reactive':
        predicted = (persistence if FORECAST == 'persistence' else ewma)(list(history))
        validation = evaluate(list(history)[-(horizon+8):], horizon=horizon)['persistence' if FORECAST == 'persistence' else 'ewma']
        STATUS['forecast_validation'] = validation
        if validation and validation['mae'] <= max(1, 0.5 * sum(s.get('rate') or 0 for s in samples.values())):
            pref = preferences(samples, CAPACITIES, predicted, history[-1], latency_slo=SLO)
            mode = 'predictive'
    target = shares(pref, CAPACITIES)
    weights, current = bounded_weights(target, previous)
    return weights, current, mode, predicted

def main():
    if POLICY not in ('reactive', 'predictive', 'round_robin', 'static_weighted', 'least_connections'):
        raise ValueError('invalid POLICY')
    Thread(target=serve_status, daemon=True).start()
    history = deque(maxlen=max(3, round(60/INTERVAL)))
    previous = {k: 1/len(NAMES) for k in NAMES}
    while True:
        began = time.monotonic()
        try:
            if POLICY in ('reactive', 'predictive'):
                samples = collect()
                if not any(s['healthy'] for s in samples.values()):
                    STATUS['mode'] = 'no_healthy_backend'
                else:
                    rate = sum(s.get('rate') or 0 for s in samples.values())
                    if all(s.get('rate') is not None for s in samples.values()):
                        history.append(rate)
                    weights, current, mode, predicted = cycle(samples, history, previous)
                    if weights != STATUS['weights']:
                        apply_weights(weights)
                        LOG.info('weights updated: %s; reason=%s', weights, mode)
                    previous = current
                    STATUS.update(weights=weights, mode=mode, prediction_enabled=mode=='predictive', forecast_rps=predicted)
            else:
                STATUS['mode'] = 'native_haproxy'
        except (requests.RequestException, ValueError) as exc:
            LOG.warning('telemetry failed; attempting static capacity fallback: %s', exc)
            try:
                fallback = {k: round(100*CAPACITIES[k]) for k in NAMES}
                apply_weights(fallback)
                STATUS.update(weights=fallback, mode='static_fallback', prediction_enabled=False)
            except (OSError, RuntimeError) as runtime_error:
                LOG.warning('fallback update failed; preserving last valid weights: %s', runtime_error)
                STATUS['mode'] = 'runtime_error'
        except (OSError, RuntimeError) as exc:
            LOG.warning('controller cycle failed; preserving last valid weights: %s', exc)
            STATUS['mode'] = 'telemetry_or_runtime_error'
        STATUS['cycle_seconds'] = time.monotonic()-began
        time.sleep(max(.1, INTERVAL-STATUS['cycle_seconds']))

if __name__ == '__main__':
    main()
