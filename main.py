import json
import time

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from entity import ChatRequest, ChatResponse, TraceStep
from agents.tools import get_hotels, get_flights, HOTEL_API_BASE, FLIGHT_API_BASE
from agents.graph import graph

conversation_history_messages = []

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Fields the router extracts from a prompt — surfaced in the trace.
ROUTER_FIELDS = [
    "intent", "sub_action",
    "city", "check_in", "check_out",
    "origin", "destination", "flight_date",
    "hotel_id", "guest_name", "guest_email", "room_type",
    "flight_id", "passenger_name", "passenger_email",
    "confirm_booking",
]

NODE_TITLES = {
    "input": "Received request",
    "router": "Analyzing request",
    "hotel_node": "Hotel agent",
    "flight_node": "Flight agent",
    "unknown_node": "General assistant",
    "generate_response": "Composing response",
}

# Tool -> (HTTP method, endpoint URL). Mirrors agents/tools.py.
TOOL_ENDPOINTS = {
    "get_hotels": ("GET", HOTEL_API_BASE),
    "search_hotel": ("GET", f"{HOTEL_API_BASE}/search"),
    "book_hotel": ("POST", f"{HOTEL_API_BASE}/book"),
    "get_flights": ("GET", FLIGHT_API_BASE),
    "search_flights": ("GET", f"{FLIGHT_API_BASE}/search"),
    "book_flight": ("POST", f"{FLIGHT_API_BASE}/book"),
}


def _non_empty(source: dict, keys: list) -> dict:
    return {k: source[k] for k in keys if source.get(k) not in (None, "", [])}


def _derive_tool(state: dict):
    """Reconstruct which tool a hotel/flight node will call, from state.

    Mirrors the branching in agents/nodes.py so the trace reflects the
    real decision without instrumenting the nodes themselves.
    """
    intent = state.get("intent")
    sub = state.get("sub_action")

    if intent == "hotel":
        if sub == "book":
            return "book_hotel", _non_empty(
                state,
                ["hotel_id", "guest_name", "guest_email", "room_type", "check_in", "check_out"],
            )
        if state.get("city"):
            return "search_hotel", _non_empty(state, ["city", "check_in", "check_out"])
        return "get_hotels", {}

    if intent == "flight":
        if sub == "book":
            return "book_flight", _non_empty(
                state, ["flight_id", "passenger_name", "passenger_email"]
            )
        if state.get("origin") and state.get("destination"):
            return "search_flights", _non_empty(state, ["origin", "destination", "flight_date"])
        if state.get("origin") or state.get("destination"):
            return None, {}
        return "get_flights", {}

    return None, {}


def _result_preview(items: list, kind: str) -> list:
    out = []
    for it in items[:3]:
        if kind == "hotel":
            label = it.get("name", "?")
        else:
            label = f"{it.get('airline', '')} {it.get('flightNumber', '')}".strip() or "?"
        rid = it.get("_id")
        out.append(f"{label} [{rid}]" if rid else label)
    if len(items) > 3:
        out.append(f"+{len(items) - 3} more")
    return out


def _build_step(step_no: int, node: str, delta: dict, merged: dict, duration_ms: int) -> TraceStep:
    detail: dict = {}

    if node == "router":
        detail = _non_empty(delta, ROUTER_FIELDS)
        tool, args = _derive_tool(merged)
        if tool:
            detail["planned_tool"] = tool
            method, url = TOOL_ENDPOINTS.get(tool, (None, None))
            if url:
                detail["endpoint"] = f"{method} {url}"
            if args:
                detail["tool_args"] = args

    elif node in ("hotel_node", "flight_node"):
        tool, args = _derive_tool(merged)
        if tool:
            detail["tool"] = tool
            method, url = TOOL_ENDPOINTS.get(tool, (None, None))
            if url:
                detail["endpoint"] = f"{method} {url}"
            if args:
                detail["args"] = args
        if delta.get("hotel_results"):
            detail["hotels_found"] = len(delta["hotel_results"])
            detail["results"] = _result_preview(delta["hotel_results"], "hotel")
        if delta.get("flight_results"):
            detail["flights_found"] = len(delta["flight_results"])
            detail["results"] = _result_preview(delta["flight_results"], "flight")
        if delta.get("response_text"):
            detail["note"] = delta["response_text"]

    elif node == "unknown_node":
        text = delta.get("response_text", "")
        if text:
            detail["preview"] = text[:200]

    elif node == "generate_response":
        detail["output_chars"] = len(delta.get("response_text", ""))

    return TraceStep(
        step=step_no,
        node=node,
        title=NODE_TITLES.get(node, node),
        detail=detail,
        duration_ms=duration_ms,
    )


def _prepare(request: ChatRequest):
    recent_pairs = conversation_history_messages[-5:]
    flattened_messages = []
    for user_msg, assistant_msg in recent_pairs:
        flattened_messages.append(user_msg)
        flattened_messages.append(assistant_msg)
    flattened_messages.append(request.message)

    initial_state = {
        "messages": flattened_messages,
        "intent": "",
        "sub_action": "",
        "city": None,
        "check_in": None,
        "check_out": None,
        "origin": None,
        "destination": None,
        "flight_date": None,
        "hotel_id": None,
        "guest_name": None,
        "guest_email": None,
        "room_type": None,
        "flight_id": None,
        "passenger_name": None,
        "passenger_email": None,
        "confirm_booking": False,
        "hotel_results": [],
        "flight_results": [],
        "booking_form": None,
        "booking_review": None,
        "response_text": "",
    }
    return initial_state, recent_pairs


def iter_graph_traced(request: ChatRequest):
    """Run the graph, yielding ('step', TraceStep) as each node finishes,
    then a final ('done', (response_text, hotels, flights, trace))."""
    initial_state, recent_pairs = _prepare(request)
    prompt = initial_state["messages"][-1]

    merged = dict(initial_state)
    trace = []
    step_no = 1

    intro = TraceStep(
        step=step_no,
        node="input",
        title=NODE_TITLES["input"],
        detail={"prompt": prompt, "context_turns": len(recent_pairs)},
        duration_ms=0,
    )
    trace.append(intro)
    yield ("step", intro)

    last = time.perf_counter()
    for update in graph.stream(initial_state, stream_mode="updates"):
        for node, delta in update.items():
            merged.update(delta)
            now = time.perf_counter()
            duration_ms = int((now - last) * 1000)
            last = now
            step_no += 1
            step = _build_step(step_no, node, delta, merged, duration_ms)
            trace.append(step)
            yield ("step", step)

    response_text = merged.get("response_text", "Something went wrong. Please try again.")
    conversation_history_messages.append((prompt, response_text))

    hotels = merged.get("hotel_results", []) or None
    flights = merged.get("flight_results", []) or None
    booking_form = merged.get("booking_form")
    booking_review = merged.get("booking_review")
    yield ("done", (response_text, hotels, flights, trace, booking_form, booking_review))


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


@app.get("/")
async def hello():
    return {"message": "Hello, World!"}


@app.get("/hotels")
async def list_hotels():
    return get_hotels.invoke({})


@app.get("/flights")
async def list_flights():
    return get_flights.invoke({})


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    response_text = "Something went wrong. Please try again."
    hotels = flights = booking_form = booking_review = None
    trace = []

    for kind, payload in iter_graph_traced(request):
        if kind == "done":
            response_text, hotels, flights, trace, booking_form, booking_review = payload

    return ChatResponse(
        response=response_text,
        hotels=hotels,
        flights=flights,
        trace=trace,
        booking_form=booking_form,
        booking_review=booking_review,
    )


@app.post("/chat/stream")
def chat_stream(request: ChatRequest):
    def event_gen():
        for kind, payload in iter_graph_traced(request):
            if kind == "step":
                yield _sse({"type": "step", "step": payload.model_dump()})
            else:
                response_text, hotels, flights, trace, booking_form, booking_review = payload
                yield _sse(
                    {
                        "type": "done",
                        "response": response_text,
                        "hotels": hotels,
                        "flights": flights,
                        "trace": [t.model_dump() for t in trace],
                        "booking_form": booking_form,
                        "booking_review": booking_review,
                    }
                )

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
