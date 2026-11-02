"""Read-only checks for a running Compose stack."""
import csv
import io
import json
from collections import Counter
import requests

def get(url, **kwargs):
    response = requests.get(url, timeout=5, **kwargs)
    response.raise_for_status()
    return response

def main():
    counts = Counter(get('http://localhost:8080/health').json()['replica'] for _ in range(30))
    print('routing replicas:', dict(counts))
    assert len(counts) == 3
    status = get('http://localhost:8081/status').json()
    print('controller:', json.dumps(status))
    targets = get('http://localhost:9090/api/v1/targets').json()['data']['activeTargets']
    print('targets:', [(x['labels']['job'], x['labels']['instance'], x['health']) for x in targets])
    assert len(targets) == 4 and all(x['health'] == 'up' for x in targets)
    for metric in ('process_cpu_seconds_total', 'process_resident_memory_bytes', 'app_requests_total', 'app_request_duration_seconds_count', 'app_inflight_requests', 'haproxy_server_status'):
        result = get('http://localhost:9090/api/v1/query', params={'query': metric}).json()['data']['result']
        print('metric:', metric, len(result))
        assert result, metric
    dashboard = get('http://localhost:3000/api/dashboards/uid/cloud-load-balancer', auth=('admin', 'admin')).json()
    print('dashboard:', dashboard['dashboard']['title'], 'panels:', len(dashboard['dashboard']['panels']))
    assert len(dashboard['dashboard']['panels']) >= 7
    print('stack verification passed')

if __name__ == '__main__':
    main()
