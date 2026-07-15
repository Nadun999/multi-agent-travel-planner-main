"""TripWeaver FastAPI backend.

Spawns the two MCP child servers on startup, runs the LangGraph agent
workflow, and exposes both a synchronous /chat endpoint and a streaming
/chat/stream endpoint that emits step + token SSE events.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agents.graph import graph
from agents.mcp_client import prime_mcp_tools, reset_mcp_cache
from agents.tools import get_flights, get_hotels
from entity import ChatRequest, ChatResponse, TraceStep


# ---- Configuration ------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent
HOTEL_SERVICE = REPO_ROOT / "mcp_servers" / "hotel_service.py"
FLIGHT_SERVICE = REPO_ROOT / "mcp_servers" / "flight_service.py"

HOTEL_MCP_PORT = int(os.getenv("HOTEL_MCP_PORT", "8001"))
FLIGHT_MCP_PORT = int(os.getenv("FLIGHT_MCP_PORT", "8002"))

# Set to "0" to skip auto-spawn (useful in environments where MCP servers are
# hosted separately). The URLs the client uses come from HOTEL_MCP_URL /
# FLIGHT_MCP_URL env vars — see agents/mcp_client.py.
AUTOSPAWN_MCP = os.getenv("AUTOSPAWN_MCP", "1") != "0"


# ---- MCP subprocess lifecycle ------------------------------------------

def _wait_for_port(host: str, port: int, timeout: float = 20.0) -> bool:
    """Poll a TCP port until it accepts connections. Returns True on success."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def _spawn_mcp_servers() -> list[subprocess.Popen]:
    """Fork the hotel + flight MCP servers as child processes."""
    procs: list[subprocess.Popen] = []
    for script in (HOTEL_SERVICE, FLIGHT_SERVICE):
        proc = subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(REPO_ROOT),
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        procs.append(proc)
    return procs


def _terminate_procs(procs: list[subprocess.Popen]) -> None:
    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass
    for p in procs:
        try:
            p.wait(timeout=5)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    procs: list[subprocess.Popen] = []
    if AUTOSPAWN_MCP:
        procs = _spawn_mcp_servers()
        # Wait for both MCP servers to accept connections.
        hotel_ok = await asyncio.to_thread(
            _wait_for_port, "127.0.0.1", HOTEL_MCP_PORT, 20.0
        )
        flight_ok = await asyncio.to_thread(
            _wait_for_port, "127.0.0.1", FLIGHT_MCP_PORT, 20.0
        )
        if not (hotel_ok and flight_ok):
            print(
                f"[TripWeaver] MCP readiness timeout — hotel={hotel_ok} flight={flight_ok}",
                flush=True,
            )
        else:
            try:
                loaded = await prime_mcp_tools()
                print(f"[TripWeaver] MCP tools loaded: {loaded}", flush=True)
            except Exception as e:
                print(f"[TripWeaver] MCP client prime failed: {e}", flush=True)

    try:
        yield
    finally:
        reset_mcp_cache()
        _terminate_procs(procs)


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Conversation history (module-scoped for a single-user demo) -------

conversation_history_messages: list[tuple[str, str]] = []


# ---- Trace instrumentation ---------------------------------------------

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
    "general_qa_node": "General travel Q&A",
    "generate_response": "Composing response",
}

# The tool -> MCP server + tool name mapping shown in the trace. This is
# how we prove to the user that the agents talk to services only through
# MCP.
HOTEL_MCP_URL = os.getenv("HOTEL_MCP_URL", f"http://127.0.0.1:{HOTEL_MCP_PORT}/mcp")
FLIGHT_MCP_URL = os.getenv("FLIGHT_MCP_URL", f"http://127.0.0.1:{FLIGHT_MCP_PORT}/mcp")

TOOL_ENDPOINTS = {
    "get_hotels": ("MCP", HOTEL_MCP_URL, "get_all_hotels"),
    "search_hotel": ("MCP", HOTEL_MCP_URL, "search_hotels"),
    "book_hotel": ("MCP", HOTEL_MCP_URL, "book_hotel"),
    "get_flights": ("MCP", FLIGHT_MCP_URL, "get_all_flights"),
    "search_flights": ("MCP", FLIGHT_MCP_URL, "search_flights"),
    "book_flight": ("MCP", FLIGHT_MCP_URL, "book_flight"),
}


def _non_empty(source: dict, keys: list) -> dict:
    return {k: source[k] for k in keys if source.get(k) not in (None, "", [])}


def _derive_tool(state: dict):
    """Reconstruct which tool a hotel/flight node will call, from state."""
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
        if not isinstance(it, dict):
            out.append(str(it))
            continue
        if kind == "hotel":
            label = it.get("name", "?")
        else:
            label = f"{it.get('airline', '')} {it.get('flightNumber', '')}".strip() or "?"
        rid = it.get("_id")
        out.append(f"{label} [{rid}]" if rid else label)
    if len(items) > 3:
        out.append(f"+{len(items) - 3} more")
    return out


def _endpoint_label(tool_name: str) -> str | None:
    entry = TOOL_ENDPOINTS.get(tool_name)
    if not entry:
        return None
    transport, url, mcp_name = entry
    return f"{transport} {url} · {mcp_name}"


def _build_step(step_no: int, node: str, delta: dict, merged: dict, duration_ms: int) -> TraceStep:
    detail: dict = {}

    if node == "router":
        detail = _non_empty(delta, ROUTER_FIELDS)
        tool, args = _derive_tool(merged)
        if tool:
            detail["planned_tool"] = tool
            label = _endpoint_label(tool)
            if label:
                detail["endpoint"] = label
            if args:
                detail["tool_args"] = args

    elif node in ("hotel_node", "flight_node"):
        tool, args = _derive_tool(merged)
        if tool:
            detail["tool"] = tool
            label = _endpoint_label(tool)
            if label:
                detail["endpoint"] = label
            if args:
                detail["args"] = args
        if delta.get("hotel_results"):
            detail["hotels_found"] = len(delta["hotel_results"])
            detail["results"] = _result_preview(delta["hotel_results"], "hotel")
        if delta.get("flight_results"):
            detail["flights_found"] = len(delta["flight_results"])
            detail["results"] = _result_preview(delta["flight_results"], "flight")
        # Surface MCP failures (SRS: FAILED tool-call status).
        if delta.get("tool_status") == "failed":
            detail["status"] = "failed"
            if delta.get("tool_error"):
                detail["error"] = delta["tool_error"]
        if delta.get("response_text"):
            detail["note"] = delta["response_text"]

    elif node == "general_qa_node":
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


# ---- Graph execution ---------------------------------------------------

def _prepare(request: ChatRequest):
    recent_pairs = conversation_history_messages[-5:]
    flattened_messages: list[str] = []
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
        "tool_status": None,
        "tool_error": None,
        "response_text": "",
    }
    return initial_state, recent_pairs


# Nodes whose token stream should be surfaced to the client. Only the
# general-QA node produces free-form conversational tokens; hotel/flight
# nodes emit deterministic text at the end.
STREAMABLE_NODES = {"general_qa_node"}


async def iter_graph_traced(request: ChatRequest):
    """Async-yield graph events for /chat and /chat/stream.

    Emits:
      ('step',  TraceStep)   — one per node completion
      ('token', str)         — one per LLM token from streamable nodes
      ('done',  tuple)       — terminal event with final response + trace
    """
    initial_state, recent_pairs = _prepare(request)
    prompt = initial_state["messages"][-1]

    merged = dict(initial_state)
    trace: list[TraceStep] = []
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

    # `astream_events` is the LangGraph-recommended way to get both
    # per-node updates AND per-token LLM chunks in a single stream.
    async for event in graph.astream_events(initial_state, version="v2"):
        etype = event.get("event")

        # Node completions — same trace step behaviour as before.
        if etype == "on_chain_end":
            name = event.get("name")
            if name not in NODE_TITLES or name == "input":
                continue
            delta = event.get("data", {}).get("output") or {}
            if not isinstance(delta, dict):
                continue
            merged.update(delta)
            now = time.perf_counter()
            duration_ms = int((now - last) * 1000)
            last = now
            step_no += 1
            step = _build_step(step_no, name, delta, merged, duration_ms)
            trace.append(step)
            yield ("step", step)

        # LLM token stream. Only surface tokens produced inside a
        # streamable node (skip the structured-output router).
        elif etype == "on_chat_model_stream":
            metadata = event.get("metadata") or {}
            node_name = metadata.get("langgraph_node")
            if node_name not in STREAMABLE_NODES:
                continue
            chunk = event.get("data", {}).get("chunk")
            content = getattr(chunk, "content", None)
            if isinstance(content, str) and content:
                yield ("token", content)
            elif isinstance(content, list):
                for piece in content:
                    if isinstance(piece, dict):
                        text = piece.get("text") or piece.get("content") or ""
                    else:
                        text = str(piece)
                    if text:
                        yield ("token", text)

    response_text = merged.get("response_text", "Something went wrong. Please try again.")
    conversation_history_messages.append((prompt, response_text))

    hotels = merged.get("hotel_results", []) or None
    flights = merged.get("flight_results", []) or None
    booking_form = merged.get("booking_form")
    booking_review = merged.get("booking_review")
    yield ("done", (response_text, hotels, flights, trace, booking_form, booking_review))


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


# ---- HTTP routes -------------------------------------------------------

@app.get("/")
async def hello():
    return {"message": "TripWeaver backend is running."}


@app.get("/hotels")
async def list_hotels():
    return await get_hotels()


@app.get("/flights")
async def list_flights():
    return await get_flights()


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    response_text = "Something went wrong. Please try again."
    hotels = flights = booking_form = booking_review = None
    trace: list[TraceStep] = []

    async for kind, payload in iter_graph_traced(request):
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
async def chat_stream(request: ChatRequest):
    async def event_gen():
        async for kind, payload in iter_graph_traced(request):
            if kind == "step":
                yield _sse({"type": "step", "step": payload.model_dump()})
            elif kind == "token":
                yield _sse({"type": "token", "text": payload})
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

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
