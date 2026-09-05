#!/usr/bin/env bats
# E2E tests — AC-MCP-101..103 — exec into the running Docker container.
# Run from the repo root with: bats tests/e2e/

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"

@test "AC-MCP-101: GET /health returns 200 with status ok" {
  docker compose -f "$REPO_ROOT/docker-compose.yml" exec -T service \
    python -c "
import json
import urllib.request

r = urllib.request.urlopen('http://localhost:8000/health')
assert r.status == 200, 'health HTTP ' + str(r.status)
assert json.load(r)['status'] == 'ok'
"
}

@test "AC-MCP-102: full REST loop — POST research, poll until completed, result.val_bpb numeric" {
  docker compose -f "$REPO_ROOT/docker-compose.yml" exec -T service \
    python -c "
import json
import time
import urllib.request

base = 'http://localhost:8000'
body = json.dumps({'topic': 'e2e service.bats research job'}).encode()
req = urllib.request.Request(
    base + '/api/v1/research', data=body,
    headers={'Content-Type': 'application/json'},
)
r = urllib.request.urlopen(req)
assert r.status == 202, 'POST research HTTP ' + str(r.status)
job = json.load(r)
job_id = job['id']
assert job_id, 'missing job id'

status = None
deadline = time.time() + 30
while time.time() < deadline:
    r = urllib.request.urlopen(base + '/api/v1/research/' + job_id)
    cur = json.load(r)
    status = cur['status']
    if status == 'completed':
        break
    if status in ('failed', 'cancelled'):
        raise SystemExit('job terminated as %s: %s' % (status, cur.get('error')))
    time.sleep(0.5)

assert status == 'completed', 'job did not complete; last status: %s' % status
val = cur['result']['val_bpb']
assert isinstance(val, (int, float)), 'val_bpb is not a number: %r' % (val,)
"
}

@test "AC-MCP-103: MCP surface reachable — tools/list names research_start" {
  docker compose -f "$REPO_ROOT/docker-compose.yml" exec -T service \
    python -c "
import json
import urllib.request

body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}}).encode()
req = urllib.request.Request(
    'http://localhost:8000/mcp', data=body,
    headers={'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'},
)
r = urllib.request.urlopen(req)
assert r.status == 200, 'MCP HTTP ' + str(r.status)
assert 'research_start' in r.read().decode(), 'tools/list response missing research_start'
"
}