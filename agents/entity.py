from typing import List, Optional, TypedDict

class GraphState(TypedDict):
    messages: List[str]

    intent: str
    sub_action: str

    city: Optional[str]
    check_in: Optional[str]
    check_out: Optional[str]

    origin: Optional[str]
    destination: Optional[str]
    flight_date: Optional[str]

    hotel_results: List[dict]
    flight_results: List[dict]

    response_text: str