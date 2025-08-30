from fastapi import APIRouter, Depends, Header, HTTPException, Response, Query, Request
from ..schemas import ValuationRequest, ValuationResponse
from ..services.valuation_service import ValuationService
from ..core.security import require_api_key, rate_limit

router = APIRouter()

def service_dep() -> ValuationService:
    # Cheap factory; if you need expensive clients, construct once and reuse.
    return ValuationService()

@router.post("/valuation", response_model=ValuationResponse)
async def post_valuation(
    body: ValuationRequest,
    response: Response,
    request: Request,
    if_none_match: str | None = Header(default=None, convert_underscores=False),
    _auth = Depends(require_api_key),     # API key guard
    _lim  = Depends(rate_limit),          # Rate limiting
    svc: ValuationService = Depends(service_dep),
):
    if not body.address.strip():
        raise HTTPException(status_code=400, detail="address is required")

    payload, from_cache, etag = await svc.value_address(body.address)
    if if_none_match and if_none_match == etag:
        response.status_code = 304
        return
    payload["cached"] = from_cache
    payload["etag"] = etag
    response.headers["ETag"] = etag
    return payload

@router.get("/valuation", response_model=ValuationResponse)
async def get_valuation(
    address: str = Query(..., min_length=4),
    response: Response = None,
    request: Request = None,
    if_none_match: str | None = Header(default=None, convert_underscores=False),
    _auth = Depends(require_api_key),
    _lim  = Depends(rate_limit),
    svc: ValuationService = Depends(service_dep),
):
    payload, from_cache, etag = await svc.value_address(address)
    if if_none_match and if_none_match == etag:
        response.status_code = 304
        return
    payload["cached"] = from_cache
    payload["etag"] = etag
    response.headers["ETag"] = etag
    return payload
