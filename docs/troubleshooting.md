# Troubleshooting

- Docker daemon unavailable: start Docker Desktop Linux containers; `docker compose config --quiet` only validates syntax.
- Prometheus target down: check `docker compose ps`, then `/targets`, then container logs.
- Controller says `static_fallback`: wait for fresh scrapes, or inspect `/metrics` on backend containers.
- Controller says `runtime_error`: verify the shared socket volume and HAProxy startup logs.
- No backend healthy: HAProxy returns 503. Restart a backend and wait for two successful health checks.
- Slow local benchmark: lower `--rate`, inspect generator CPU, and check `generator_overload` rows.
