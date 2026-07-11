from pydantic import BaseModel
from typing import Any, Dict, List, Optional

class ChatRequest(BaseModel):
    message: str


class TraceStep(BaseModel):
    step: int
    node: str
    title: str
    detail: Dict[str, Any] = {}
    duration_ms: int = 0


class BookingField(BaseModel):
    name: str
    label: str
    type: str = "text"  # text | email | date | select
    value: Optional[str] = None
    options: Optional[List[str]] = None


class BookingForm(BaseModel):
    kind: str  # "hotel" | "flight"
    title: str
    fields: List[BookingField]


class BookingReviewItem(BaseModel):
    label: str
    value: Optional[str] = None


class BookingReview(BaseModel):
    kind: str  # "hotel" | "flight"
    title: str
    items: List[BookingReviewItem]


class ChatResponse(BaseModel):
    response: str
    hotels: Optional[List[dict]] = None
    flights: Optional[List[dict]] = None
    trace: Optional[List[TraceStep]] = None
    booking_form: Optional[BookingForm] = None
    booking_review: Optional[BookingReview] = None
