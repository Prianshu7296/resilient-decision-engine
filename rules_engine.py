import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config" / "vendor_rules.json"

def load_config():
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)

def _value(data, path):
    current = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current

def _matches(actual, operator, expected):
    if operator == "eq": return actual == expected
    if operator == "neq": return actual != expected
    if operator == "gt": return actual is not None and actual > expected
    if operator == "gte": return actual is not None and actual >= expected
    if operator == "lt": return actual is not None and actual < expected
    if operator == "lte": return actual is not None and actual <= expected
    if operator == "in": return actual in expected
    if operator == "contains": return expected in actual if actual is not None else False
    if operator == "not_contains": return expected not in actual if actual is not None else True
    if operator == "exists": return (actual is not None) == bool(expected)
    raise ValueError(f"Unsupported rule operator: {operator}")

def evaluate(payload):
    config = load_config()
    trace = []
    for rule in config["rules"]:
        outcomes = []
        for condition in rule["conditions"]:
            actual = _value(payload, condition["field"])
            passed = _matches(actual, condition["operator"], condition.get("value"))
            outcomes.append(passed)
            trace.append({
                "rule_id": rule["id"], "field": condition["field"],
                "operator": condition["operator"], "expected": condition.get("value"),
                "actual": actual, "passed": passed
            })
        matched = all(outcomes) if rule.get("match", "all") == "all" else any(outcomes)
        if matched:
            return {"decision": rule["decision"], "explanation": rule["reason"],
                    "rule_trace": trace, "matched_rule": rule["id"]}
    fallback = config.get("default", {})
    return {"decision": fallback.get("decision", "MANUAL_REVIEW"),
            "explanation": fallback.get("reason", "No rule matched; manual review required."),
            "rule_trace": trace, "matched_rule": "default"}
