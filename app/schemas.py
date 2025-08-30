from pydantic import BaseModel, Field

class ValuationRequest(BaseModel):
    address: str = Field(min_length=4, strip_whitespace=True)

class Range(BaseModel):
    low: int
    high: int

class ValuationResponse(BaseModel):
    address: str
    currency: str = "CAD"
    valuation: int
    range: Range
    confidence: int = Field(ge=0, le=100)
    trend_mom_pct: float
    comparables_used: int
    insights: list[str]
    sparkline_index_12m: list[int]
    factors: dict
    disclaimer: str
    cached: bool = False
    etag: str | None = None
