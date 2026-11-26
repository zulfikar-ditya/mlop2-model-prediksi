from __future__ import annotations

import os
import secrets
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.fraud_model import FraudModel

app = FastAPI(title="Account Opening Fraud API")
model = FraudModel()

Binary = Literal[0, 1]
MISSING = -1


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.environ.get("API_KEY")
    if not expected:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "API_KEY is not configured")
    if x_api_key is None or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing x-api-key")


class Application(BaseModel):
    """29 model features. Fields the dataset marks missing with -1 are optional and default to -1."""

    income: float = Field(ge=0, le=1)
    name_email_similarity: float = Field(ge=0, le=1)
    customer_age: int = Field(ge=0, le=120)
    days_since_request: float = Field(ge=0)
    intended_balcon_amount: float
    payment_type: Literal["AA", "AB", "AC", "AD", "AE"]
    zip_count_4w: int = Field(ge=0)
    velocity_6h: float
    velocity_24h: float
    velocity_4w: float
    bank_branch_count_8w: int = Field(ge=0)
    date_of_birth_distinct_emails_4w: int = Field(ge=0)
    employment_status: Literal["CA", "CB", "CC", "CD", "CE", "CF", "CG"]
    credit_risk_score: int
    email_is_free: Binary
    housing_status: Literal["BA", "BB", "BC", "BD", "BE", "BF", "BG"]
    phone_home_valid: Binary
    phone_mobile_valid: Binary
    has_other_cards: Binary
    proposed_credit_limit: float = Field(ge=0)
    foreign_request: Binary
    source: Literal["INTERNET", "TELEAPP"]
    device_os: Literal["linux", "macintosh", "other", "windows", "x11"]
    keep_alive_session: Binary

    prev_address_months_count: int = Field(default=MISSING, ge=MISSING)
    current_address_months_count: int = Field(default=MISSING, ge=MISSING)
    bank_months_count: int = Field(default=MISSING, ge=MISSING)
    session_length_in_minutes: float = Field(default=MISSING, ge=MISSING)
    device_distinct_emails_8w: int = Field(default=MISSING, ge=MISSING)


class Prediction(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_name: str | None = None
    model_version: str | None = None
    fraud_score: float | None = None
    is_fraud: bool | None = None
    threshold: float | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/predict", response_model=Prediction, response_model_exclude_none=True, dependencies=[Depends(require_api_key)])
def predict(
    payload: Application,
    threshold: float | None = Query(default=None, ge=0, le=1, description="override the default FPR-5% threshold"),
    fields: str | None = Query(default=None, description="comma-separated subset of model_name,model_version,fraud_score,is_fraud,threshold"),
) -> dict[str, object]:
    result = model.predict([payload.model_dump()], threshold)[0]
    if fields:
        wanted = {f.strip() for f in fields.split(",")}
        result = {k: v for k, v in result.items() if k in wanted}
    return result
