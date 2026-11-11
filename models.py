from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List

class VendorApplication(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=3, max_length=100)
    vendor_name: str = Field(min_length=2, max_length=150)
    country: str = Field(min_length=2, max_length=80)
    annual_revenue: float = Field(gt=0)
    risk_score: int = Field(ge=0, le=100, description="0 = lowest risk, 100 = highest risk")
    documents: List[str] = Field(default_factory=list)
    simulate_dependency_failures: int = Field(default=0, ge=0, le=5)

class DecisionResponse(BaseModel):
    request_key: str
    status: str
    decision: Optional[str] = None
    explanation: Optional[str] = None
    rule_trace: list = Field(default_factory=list)
    retry_count: int = 0
    duplicate: bool = False
