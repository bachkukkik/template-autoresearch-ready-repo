## When to use this example

Load this file when updating an existing doc in `docs/`. It covers the three most common update scenarios:

1. Adding a new **What Fails / Resolution** pair
2. Updating **Verification** steps
3. Updating the **How** section for a configuration change

It also shows how to update `## What Works` when a previously failing behavior is fixed.

---

## Scenario 1: Adding a new "What Fails / Resolution" pair

A new issue has been discovered with the RustFS service. The doc `13-rustfs.md` already exists. The update adds one bullet to `## What Fails` and one matching bullet to `## Resolution`.

### Before (excerpt)

```markdown
## What Fails

- **Large multipart uploads:** Objects larger than 5 GB return a `501 Not Implemented` for single-request PUT.
- **Versioning:** S3 versioning API endpoints return `501`.

## Resolution

- **Large multipart uploads:** Always use multipart upload for objects over 100 MB.
- **Versioning:** No workaround. Treat overwrites as destructive.
```

### After (excerpt)

```markdown
## What Fails

- **Large multipart uploads:** Objects larger than 5 GB return a `501 Not Implemented` for single-request PUT.
- **Versioning:** S3 versioning API endpoints return `501`.
- **Concurrent writes:** Two PUT requests to the same key within the same second produce a corrupted object. No locking or conflict detection exists.

## Resolution

- **Large multipart uploads:** Always use multipart upload for objects over 100 MB.
- **Versioning:** No workaround. Treat overwrites as destructive.
- **Concurrent writes:** Serialize writes to the same key at the application layer using a distributed lock (e.g., Redis `SETNX`). Alternatively, design key schemas that avoid concurrent writes to the same path.
```

### Rules

- Append new failures at the end of the `## What Fails` list unless they relate to an existing failure — in that case, place them adjacent.
- The `## Resolution` list must always mirror the order and count of `## What Fails` exactly.
- Never remove an existing failure/resolution pair unless the issue is confirmed fixed. If it is fixed, move the bullet from `## What Fails` to `## What Works` and remove the matching resolution.

---

## Scenario 2: Updating Verification steps

The health check endpoint has changed from `/minio/health/live` to `/healthz`. Update the `## Verification` section.

### Before

```markdown
## Verification

```bash
docker compose ps rustfs
curl -s http://localhost:9000/minio/health/live
aws --endpoint-url http://localhost:9000 s3 ls --no-sign-request
```

All three commands must return exit code 0.
```

### After

```markdown
## Verification

```bash
docker compose ps rustfs
curl -sf http://localhost:9000/healthz
aws --endpoint-url http://localhost:9000 s3 ls --no-sign-request
```

All three commands must return exit code 0.
```

### Rules

- Every command in `## Verification` must be runnable as-is. No placeholders.
- State the success criterion explicitly (exit code, expected output, etc.).
- Do not add commands that require manual inspection without stating what to look for.

---

## Scenario 3: Configuration change in "How"

A new environment variable `RUSTFS_MAX_UPLOAD_SIZE` has been added to control the maximum single-request upload size.

### Before (excerpt)

```markdown
| Parameter | Value | Notes |
|-----------|-------|-------|
| `RUSTFS_ROOT` | `/data` | Bind-mounted from host `/opt/rustfs` |
| `RUSTFS_PORT` | `9000` | HTTP only |
| `RUSTFS_UID` | `10001` | Non-root user |
| `RUSTFS_LOG_LEVEL` | `info` | Set to `debug` for troubleshooting |
```

### After (excerpt)

```markdown
| Parameter | Value | Notes |
|-----------|-------|-------|
| `RUSTFS_ROOT` | `/data` | Bind-mounted from host `/opt/rustfs` |
| `RUSTFS_PORT` | `9000` | HTTP only |
| `RUSTFS_UID` | `10001` | Non-root user |
| `RUSTFS_LOG_LEVEL` | `info` | Set to `debug` for troubleshooting |
| `RUSTFS_MAX_UPLOAD_SIZE` | `5368709120` | Max single-request upload in bytes (default 5 GB). Set to `0` to disable limit. |
```

### Rules

- Add rows to existing tables in their logical position. Do not recreate the table from scratch unless the schema has changed.
- If a parameter replaces a deprecated one, note the deprecation in the `Notes` column of the old parameter and add the new parameter.
- Update any `## Verification` commands that depend on the changed configuration.

---

## General rules for all updates

1. **Never renumber the doc.** The file number (`NN`) and title are permanent.
2. **Never merge, split, or rename sections.** All eight sections must remain in order.
3. **Maintain present tense, active voice.** Do not introduce past tense or passive voice during edits.
4. **Keep the 1:1 correspondence** between `## What Fails` and `## Resolution`. Count them after every edit.
5. **Update `## Verdict`** if the update changes the overall assessment of the component. If it doesn't, leave it unchanged.
