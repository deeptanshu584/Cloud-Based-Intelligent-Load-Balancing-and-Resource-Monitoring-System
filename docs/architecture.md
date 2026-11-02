# Architecture notes

The Flask replicas share an image but no mutable state. HAProxy owns health checking and request dispatch. Its runtime socket stays on a Docker volume shared only with the controller. Prometheus scrapes replica and proxy endpoints; the controller is outside the per-request path. Each policy switch recreates HAProxy with the requested native algorithm or controller-managed weighted round robin. Grafana reads Prometheus through an internal Docker network.
