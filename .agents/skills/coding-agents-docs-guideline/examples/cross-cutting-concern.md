## When to use this example

Load this file when documenting a cross-cutting concern in `docs/` — something that spans multiple services rather than being a single container or daemon. Examples include logging, CI/CD, secrets management, networking, or monitoring. It shows how `## How` differs when there is no single service to configure.

---

## Complete Example

```markdown
# 14 — Centralized Logging

## What

All services emit structured JSON logs to stdout. Docker captures these logs and forwards them to a centralized Loki instance for querying and alerting.

## Why

- Scattered `docker compose logs` calls are insufficient for debugging issues that cross service boundaries.
- Structured JSON logs enable filtering by request ID, service name, and severity without ad-hoc parsing.
- Loki was chosen over Elasticsearch for its lower memory footprint and native Grafana integration.

## How

Each service container writes JSON-formatted logs to stdout. A Promtail sidecar ships them to Loki.

### Log format

Every log line must be valid JSON with these fields:

| Field | Type | Required | Example |
|-------|------|----------|---------|
| `ts` | ISO 8601 string | yes | `2025-01-15T08:30:00Z` |
| `level` | string enum | yes | `info`, `warn`, `error` |
| `msg` | string | yes | `request completed` |
| `service` | string | yes | `api-gateway` |
| `request_id` | string | no | `abc-123-def` |
| `duration_ms` | integer | no | `42` |

### Promtail configuration

Promtail runs as a global Docker logging driver. No per-service configuration is required.

```yaml
# /etc/promtail/config.yml
clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        target_label: 'container'
```

### Querying

```bash
curl -s "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={container="api-gateway"} | json | level="error"' \
  --data-urlencode "start=$(date -d '1 hour ago' +%s)000000000" \
  --data-urlencode "end=$(date +%s)000000000" | jq .
```

### Adding a new service

No extra steps. Any container that writes JSON to stdout with the required fields is automatically collected by Promtail.

## Verification

```bash
docker compose logs api-gateway --tail 1 | jq .ts .level .service
curl -s "http://localhost:3100/loki/api/v1/labels" | jq .
```

The first command must return valid JSON with `ts`, `level`, and `service` fields. The second must include `container` in the label list.

## What Works

- All services emit valid JSON logs without exception
- Promtail discovers new containers within 30 seconds of startup
- Log queries across multiple services return correlated results when filtered by `request_id`
- Grafana Explore provides a usable query interface for ad-hoc debugging

## What Fails

- **High-volume services:** Services logging more than 10 000 lines per minute cause Promtail to drop entries. Loki ingest rate limits trigger silently.
- **Log rotation:** Docker's default json-file driver does not rotate logs. Disk fills on the host after sustained high-volume logging.
- **Retroactive queries:** Logs older than the Loki retention period (7 days) are permanently deleted and unrecoverable.

## Resolution

- **High-volume services:** Set `LOKI_INGEST_RATE_LIMIT_BYTES` to `50MB` and increase Promtail's `batch_size` to `1MB`. For services exceeding this, add a local file buffer with Promtail's `wal` directory.
- **Log rotation:** Configure Docker's `log-opts` in `daemon.json` with `max-size: 50m` and `max-file: 5` per container.
- **Retroactive queries:** No workaround within Loki. Export critical logs to an S3 bucket via the Loki compactor's `storage_config` for long-term retention.

## Verdict

Centralized logging with Loki and Promtail handles the stack's debugging needs for normal traffic. High-volume services and long-term retention require additional configuration, but the default setup is fit for day-to-day operations.
```

---

## Key patterns to notice

1. **`## What`** describes the concern, not a single service. It names the mechanism and its scope.
2. **`## How`** uses `###` sub-headings for each distinct mechanism (log format, Promtail config, querying, adding a new service). This is the expected structure for cross-cutting concerns.
3. **Tables** are used for structured specs (log fields, their types, and examples).
4. **"Adding a new service"** is included as a sub-section because cross-cutting docs must explain how a new service adopts the pattern.
5. **`## Verification`** includes a command that tests the consumer side (querying) in addition to the producer side (log format).
6. **`## What Fails`** and **`## Resolution`** maintain 1:1 correspondence. Each failure has exactly one resolution, in the same order.
