## When to use this example

Load this file when documenting a new service, container, or daemon in `docs/`. It shows every section of the template filled out with realistic content. Use it as a reference for tone, density, and formatting.

---

## Complete Example

```markdown
# 13 — RustFS

## What

RustFS is a custom S3-compatible object store backed by the local filesystem. It acts as the primary persistence layer for uploaded assets and pipeline artifacts.

## Why

- MinIO and similar object stores add operational weight (Java runtime, separate cluster) that is unnecessary for a single-node deployment.
- A local-filesystem backend eliminates network overhead for read/write operations on the same host.
- S3-compatible API keeps the door open for migrating to a real object store later without changing consumer code.

## How

RustFS runs as a Docker container with a bind-mounted data directory. It listens on port 9000 and exposes an S3-compatible HTTP API.

| Parameter | Value | Notes |
|-----------|-------|-------|
| `RUSTFS_ROOT` | `/data` | Bind-mounted from host `/opt/rustfs` |
| `RUSTFS_PORT` | `9000` | HTTP only; TLS terminated by the reverse proxy |
| `RUSTFS_UID` | `10001` | Non-root user; must match host directory ownership |
| `RUSTFS_LOG_LEVEL` | `info` | Set to `debug` for troubleshooting |

### Authentication

All requests require an `Authorization: AWS4-HMAC-SHA256` header. Credentials are provisioned via environment variables:

```bash
RUSTFS_ACCESS_KEY=localdev
RUSTFS_SECRET_KEY=localdevsecret
```

### Bucket layout

| Bucket | Purpose | Retention |
|--------|---------|-----------|
| `uploads` | User-submitted files | 90 days |
| `artifacts` | CI pipeline outputs | 30 days |
| `backups` | Database snapshots | 365 days |

### Startup

```bash
docker compose up -d rustfs
```

The container performs a health check against `GET /minio/health/live` every 10 seconds.

## Verification

```bash
docker compose ps rustfs
curl -s http://localhost:9000/minio/health/live
aws --endpoint-url http://localhost:9000 s3 ls --no-sign-request
```

All three commands must return exit code 0.

## What Works

- PUT/GET of objects up to 5 GB via multipart upload
- Bucket creation and listing via the S3 API
- Automatic directory creation for nested key prefixes
- Health check endpoint responds within 50 ms under normal load
- Non-root container execution with UID 10001

## What Fails

- **Large multipart uploads:** Objects larger than 5 GB return a `501 Not Implemented` for single-request PUT. Multipart is required.
- **Versioning:** S3 versioning API endpoints return `501`. Object overwrite is destructive.
- **Bucket policies:** IAM-style bucket policies are ignored. Access control is all-or-nothing per credential pair.

## Resolution

- **Large multipart uploads:** Always use multipart upload for objects over 100 MB. The SDK handles this automatically when `multipart_threshold` is configured.
- **Versioning:** No workaround. Treat overwrites as destructive. Implement application-level versioning in the key schema (e.g., `uploads/{id}/{version}`).
- **Bucket policies:** Restrict access at the network level. Place RustFS on an internal-only Docker network and expose it solely to authorized services.

## Verdict

RustFS covers the core S3 read/write surface well for a single-node deployment. Lack of versioning and bucket policies makes it unsuitable for multi-tenant or compliance-sensitive workloads, but it is fit for purpose as a lightweight internal object store.
```

---

## Key patterns to notice

1. **`## What`** is exactly one sentence. It names the thing and its role. No rationale here.
2. **`## Why`** uses bullets. Each bullet is one reason, stated directly.
3. **`## How`** is the longest section. It uses tables for structured data, code blocks for commands, and `###` sub-headings to break up distinct mechanisms.
4. **`## Verification`** contains only runnable commands with a clear success criterion ("All three commands must return exit code 0").
5. **`## What Works`** and **`## What Fails`** use consistent bullet format. Failure bullets lead with a **bold issue name**.
6. **`## Resolution`** mirrors the order of `## What Fails` exactly — one resolution per failure.
7. **`## Verdict`** is two sentences: what works, what doesn't, and the net conclusion.
