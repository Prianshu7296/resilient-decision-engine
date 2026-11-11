# Resilient Decision Engine

A small, configurable workflow decision platform demonstrating vendor approval, rule evaluation, lifecycle state, audit history, idempotency, and retry handling.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://127.0.0.1:8000 for the landing page and http://127.0.0.1:8000/docs for interactive API documentation.

## Example request

```bash
curl -X POST http://127.0.0.1:8000/requests \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: vendor-1001" \
  -d '{
    "request_id": "vendor-1001",
    "vendor_name": "Northwind Supplies",
    "country": "India",
    "annual_revenue": 250000,
    "risk_score": 20,
    "documents": ["tax_certificate", "registration"]
  }'
```

Possible decisions are `APPROVED`, `REJECTED`, and `MANUAL_REVIEW`. Workflow status is tracked separately (`RECEIVED`, `PROCESSING`, `RETRY_PENDING`, `COMPLETED`).

## Demo scenarios

1. Approved: risk score <= 30 and annual revenue >= 100000.
2. Rejected: risk score > 80.
3. Manual review: medium risk or no matching rule.
4. Idempotency: submit the same `Idempotency-Key` twice; the second response is marked `duplicate`.
5. Dependency failure: set `simulate_dependency_failures` to `1`, then call `POST /requests/{request_key}/retry`.
6. Audit: inspect `GET /requests/{request_key}/audit`.

## Configuration

Edit `config/vendor_rules.json`. Rules are evaluated in order and the first matching rule wins. Each rule contains an ID, conditions, decision, and human-readable reason. Supported operators: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `contains`, `not_contains`, and `exists`. Conditions default to `all`; set `match` to `any` to use OR semantics. The config is read for each evaluation, so rule edits take effect without restarting the app.

## API

- `GET /` - landing page
- `GET /health` - health check
- `GET /config` - current rules configuration
- `POST /requests` - validate and process a vendor application
- `GET /requests` - list workflow requests
- `GET /requests/{request_key}` - request state and decision
- `GET /requests/{request_key}/audit` - chronological audit events
- `POST /requests/{request_key}/retry` - retry a pending workflow

## Architecture and design decisions

The implementation is a modular monolith: API, validation models, rule evaluation, workflow orchestration, and persistence are separated into modules but run as one deployable process. SQLite keeps the demo self-contained. JSON configuration separates policy from execution code. Every decision includes a rule trace with the actual value, operator, expected value, and result.

The idempotency key is the primary key for a workflow request. A repeated submission returns the existing record instead of creating another workflow. The simulated vendor-registry dependency can fail a configured number of times; each failure moves the workflow to `RETRY_PENDING` and records an audit event. A retry endpoint resumes processing.

## Tests

```bash
pytest -q
```

Tests cover approval, invalid input, duplicate submissions, dependency retry, rejection, manual review, and audit history.

## Assumptions and limitations

- The external dependency is simulated; no third-party service is called.
- The API is synchronous for this demonstration. A production implementation would use a durable queue and background workers.
- SQLite is suitable for a local demo, not high-concurrency production workloads. PostgreSQL would be a natural next step.
- Retry scheduling is caller-driven through the retry endpoint. Production retry policy should add exponential backoff, attempt limits, and dead-letter handling.
- The current example models a single vendor approval workflow, while the JSON rule format is reusable. A next iteration could make stage definitions and transitions configurable too.
- For production use, add authentication, authorization, rate limiting, structured observability, database migrations, and transactional outbox patterns.
