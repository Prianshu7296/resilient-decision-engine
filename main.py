from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from typing import Optional
from models import VendorApplication, DecisionResponse
from database import init_db, create_or_get_request, get_request, get_audit, list_requests, update_request
from rules_engine import load_config, evaluate
from workflow import process_request, retry_request

app = FastAPI(
    title="Resilient Decision Engine",
    description="Configurable vendor approval workflow with auditability, retries and idempotency.",
    version="1.0.0",
)

@app.on_event("startup")
def startup():
    init_db()

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html><head><title>Resilient Decision Engine</title>
    <style>
      body{font:16px system-ui;max-width:850px;margin:48px auto;padding:0 20px;color:#172033}
      code{background:#f1f3f5;padding:3px 6px;border-radius:4px}
      a{color:#1458a6} .box{background:#f6f8fa;padding:18px;border-radius:10px}
    </style></head><body>
    <h1>Resilient Decision Engine</h1>
    <p>Configurable vendor approval workflow demo.</p>
    <div class="box">
      <p><b>API documentation:</b> <a href="/docs">Open Swagger UI</a></p>
      <p><b>Health:</b> <a href="/health">/health</a></p>
      <p><b>Active rules:</b> <a href="/config">/config</a></p>
      <p><b>Requests:</b> <a href="/requests">/requests</a></p>
    </div>
    <p>Submit a vendor application with <code>POST /requests</code>. Use the <code>Idempotency-Key</code> header to safely retry client submissions.</p>
    </body></html>
    """

@app.get("/health")
def health():
    return {"status": "ok", "service": "resilient-decision-engine"}

@app.get("/config")
def config():
    return load_config()

@app.post("/requests", response_model=DecisionResponse)
def submit_request(payload: VendorApplication, idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    key = idempotency_key or payload.request_id
    if not key:
        raise HTTPException(status_code=400, detail="Provide request_id or Idempotency-Key")
    record, created = create_or_get_request(key, payload.model_dump())
    if not created:
        return DecisionResponse(**record, duplicate=True)
    result = process_request(key, payload.model_dump())
    return DecisionResponse(**result, duplicate=False)

@app.get("/requests")
def requests():
    return {"items": list_requests()}

@app.get("/requests/{request_key}")
def request_detail(request_key: str):
    record = get_request(request_key)
    if not record:
        raise HTTPException(status_code=404, detail="Request not found")
    return record

@app.get("/requests/{request_key}/audit")
def request_audit(request_key: str):
    if not get_request(request_key):
        raise HTTPException(status_code=404, detail="Request not found")
    return {"request_key": request_key, "events": get_audit(request_key)}

@app.post("/requests/{request_key}/retry")
def retry(request_key: str):
    record = get_request(request_key)
    if not record:
        raise HTTPException(status_code=404, detail="Request not found")
    return retry_request(request_key, record["payload"])
