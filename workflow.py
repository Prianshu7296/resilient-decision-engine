from database import get_request, update_request
from rules_engine import evaluate

def process_request(key, payload):
    record = get_request(key)
    if not record:
        raise ValueError("Request does not exist")
    if record["status"] in ("COMPLETED", "FAILED"):
        return record

    update_request(key, status="PROCESSING", event="WORKFLOW_STARTED", details={"stage": "rules_evaluation"})
    # Simulated dependency: failures are consumed one attempt at a time.
    failures_left = int(payload.get("simulate_dependency_failures", 0))
    current = get_request(key)
    attempts = current["retry_count"]
    if failures_left > 0:
        failures_left -= 1
        payload["simulate_dependency_failures"] = failures_left
        update_request(key, retry_count=attempts + 1, status="RETRY_PENDING",
                       event="DEPENDENCY_FAILURE",
                       details={"dependency": "vendor_registry", "attempt": attempts + 1,
                                "remaining_simulated_failures": failures_left})
        # Persist the decremented failure counter so a retry can recover.
        update_payload(key, payload)
        return get_request(key)

    result = evaluate(payload)
    update_request(key, status="COMPLETED", decision=result["decision"],
                   explanation=result["explanation"], rule_trace=result["rule_trace"],
                   event="DECISION_MADE",
                   details={"decision": result["decision"], "matched_rule": result["matched_rule"],
                            "explanation": result["explanation"]})
    return get_request(key)

def update_payload(key, payload):
    import json
    from database import connect, now
    with connect() as c:
        c.execute("UPDATE workflow_requests SET payload=?,updated_at=? WHERE request_key=?",
                  (json.dumps(payload), now(), key))

def retry_request(key, payload):
    record = get_request(key)
    if record["status"] != "RETRY_PENDING":
        return {"request_key": key, "status": record["status"],
                "message": "Retry is only available for RETRY_PENDING requests."}
    update_request(key, status="PROCESSING", event="RETRY_STARTED",
                   details={"retry_count": record["retry_count"]})
    return process_request(key, payload)
