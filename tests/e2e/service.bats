#!/usr/bin/env bats
# E2E tests — AC-MCP-101..104 — exec into the running Docker container.
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

@test "AC-MCP-104: two topics with inline corpora complete with distinct results" {
  docker compose -f "$REPO_ROOT/docker-compose.yml" exec -T service \
    python -c "
import json
import time
import urllib.request

base = 'http://localhost:8000'


def start(topic, texts):
    body = json.dumps({
        'topic': topic,
        'params': {'corpus': {'texts': texts}},
    }).encode()
    req = urllib.request.Request(
        base + '/api/v1/research', data=body,
        headers={'Content-Type': 'application/json'},
    )
    r = urllib.request.urlopen(req)
    assert r.status == 202, 'POST %s HTTP %s' % (topic, r.status)
    return json.load(r)


def wait_completed(job_id):
    status = None
    deadline = time.time() + 30
    while time.time() < deadline:
        r = urllib.request.urlopen(base + '/api/v1/research/' + job_id)
        cur = json.load(r)
        status = cur['status']
        if status == 'completed':
            return cur
        if status in ('failed', 'cancelled'):
            raise SystemExit('job terminated as %s: %s' % (status, cur.get('error')))
        time.sleep(0.5)
    raise SystemExit('job %s did not complete; last status: %s' % (job_id, status))

job_a = start('e2e multi-topic alpha', [
    {'title': 'alpha source', 'content': 'First inline corpus text for topic A.'},
])
job_b = start('e2e multi-topic beta', [
    {'title': 'beta source one', 'content': 'Second inline corpus text for topic B.'},
    {'title': 'beta source two', 'content': 'Third inline corpus text for topic B.'},
])
done_a = wait_completed(job_a['id'])
done_b = wait_completed(job_b['id'])

topic_a = done_a['result']['topic']
topic_b = done_b['result']['topic']
assert topic_a != topic_b, 'topics should differ: %r vs %r' % (topic_a, topic_b)
for done, expect in ((done_a, 'e2e multi-topic alpha'), (done_b, 'e2e multi-topic beta')):
    assert done['result']['topic'] == expect, 'result topic echo mismatch'
    val = done['result']['val_bpb']
    assert isinstance(val, (int, float)), 'val_bpb is not a number: %r' % (val,)
"
}