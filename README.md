# TripWeaver — MCP-based multi-agent travel planner

A conversational travel concierge with a React chat interface, a FastAPI
LangGraph backend, and two Model Context Protocol (MCP) servers that stand
between the agents and the external hotel and flight services.

Ask in plain language ("flights from CMB to BKK next Friday", "book me a
hotel in Bangkok", "what should I pack for Iceland?") — an intent-routed
graph of specialised agents interprets, gathers data through MCP tools,
asks follow-up questions when it needs more, shows a review card before
any booking is placed, and streams the answer back token-by-token.

---

## Architecture

```
┌────────────────────┐          ┌───────────────────────────────────────┐
│  React + Vite UI   │  HTTP    │             FastAPI backend           │
│  (streams via SSE) │◀────────▶│  ┌─────────────────────────────────┐  │
└────────────────────┘          │  │        LangGraph workflow       │  │
                                │  │                                 │  │
                                │  │   router  ─┬─▶ hotel_node       │  │
                                │  │            ├─▶ flight_node      │  │
                                │  │            └─▶ general_qa_node  │  │
                                │  │                                 │  │
                                │  └───────────────┬─────────────────┘  │
                                │                  │ MCP client         │
                                │                  ▼                    │
                                │  ┌──────────────────────────────────┐ │
                                │  │  MultiServerMCPClient            │ │
                                │  └──┬───────────────────────────┬───┘ │
                                └─────┼───────────────────────────┼─────┘
                                      │ streamable_http           │
                                ┌─────▼────────┐         ┌────────▼─────┐
                                │ Hotel MCP    │         │ Flight MCP   │
                                │ :8001        │         │ :8002        │
                                └──────┬───────┘         └──────┬───────┘
                                       │                        │
                                       ▼                        ▼
                                 ┌────────────────────────────────┐
                                 │   Convex travel API (upstream) │
                                 └────────────────────────────────┘
```

- **React frontend** (`frontend/`) — token-streaming chat UI. Renders
  boarding-pass and hotel-key result cards, an inline booking form, a
  review-then-confirm gate before any booking is placed, and a live
  "Thinking" trace of the agent workflow.
- **FastAPI backend** (`main.py`) — spawns the two MCP servers as child
  processes on startup, runs the LangGraph workflow, and exposes both a
  `POST /chat` endpoint (whole response) and a `POST /chat/stream` endpoint
  (SSE) that emits three event kinds:
  - `step` — one per node completion (with the tool it called, args,
    result count, and duration)
  - `token` — one per LLM token from the general Q&A node
  - `done` — terminal event with the final response, structured hotel /
    flight results, and the full trace
- **LangGraph agents** (`agents/`) — `router` extracts intent + entities
  and drives the graph to one of `hotel_node`, `flight_node`, or
  `general_qa_node`. Nodes are async and reach external services only
  through the MCP client.
- **MCP servers** (`mcp_servers/`) — `hotel_service.py` on port 8001 and
  `flight_service.py` on port 8002. Each is a standalone FastMCP process
  exposing MCP tools that call the Convex upstream. Nothing in `agents/`
  imports `requests` or a URL.

---

## Setup

### 1. Create the virtualenv

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment

Copy `.env.example` to `.env` and set your OpenAI key:

```bash
cp .env.example .env
# then edit .env and set OPENAI_API_KEY
```

`.env` is gitignored — never commit it.

Optional overrides:

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | OpenAI credential used by the LLM. |
| `HOTEL_MCP_PORT` | `8001` | Local port for the hotel MCP subprocess. |
| `FLIGHT_MCP_PORT` | `8002` | Local port for the flight MCP subprocess. |
| `HOTEL_MCP_URL` | `http://127.0.0.1:8001/mcp` | Full endpoint the client talks to. Point this at a remote MCP host for split deployments. |
| `FLIGHT_MCP_URL` | `http://127.0.0.1:8002/mcp` | ditto for flights. |
| `AUTOSPAWN_MCP` | `1` | Set to `0` to skip subprocess spawn (use with the URL overrides above when MCP is hosted separately). |

### 3. Run everything

**One-command backend + MCP servers.** The FastAPI backend spawns
`mcp_servers/hotel_service.py` and `mcp_servers/flight_service.py` as child
processes on startup, waits for both ports, primes the MCP tool cache, and
serves. On shutdown it terminates both children cleanly.

```bash
python main.py
```

Look for this line to confirm the MCP layer is wired up:

```
[TripWeaver] MCP tools loaded: ['book_flight', 'book_hotel', 'get_all_flights', ... 'search_hotels']
```

**Frontend (separate terminal):**

```bash
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite (default `http://localhost:5173`).

---

## MCP setup guide

Full details live in [MCP.md](MCP.md), including how each tool maps to the
Convex upstream and how to add a new provider without touching agent code.

The short version:

1. Each MCP server runs as a standalone Python process (`streamable-http`
   transport). `mcp_servers/hotel_service.py` runs on `:8001`,
   `mcp_servers/flight_service.py` runs on `:8002`.
2. Every MCP server exposes typed `@mcp.tool()` functions. Signatures are
   the source of truth — the LangChain adapter builds tool schemas
   automatically.
3. `agents/mcp_client.py` holds a singleton `MultiServerMCPClient`
   pointing at both URLs. `call_mcp(name, **args)` is the only entry
   point.
4. `agents/tools.py` is a thin façade — one async wrapper per tool. No
   HTTP, no URLs, no `requests`. Adding a new provider means writing a
   new MCP server and one line in `MCP_SERVERS`.

---

## API endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/hotels` | GET | Full hotel list (via `get_all_hotels` MCP tool). |
| `/flights` | GET | Full flight list (via `get_all_flights` MCP tool). |
| `/chat` | POST | Non-streaming chat. Returns full response + trace. |
| `/chat/stream` | POST | SSE stream of `step`, `token`, `done` events. |

### Chat example

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "flights from SIN to KUL"}'
```

**Other queries to try:**
- `"show me all hotels"`
- `"hotels in Bangkok next weekend"`
- `"i want to book a flight from CMB to BKK"`
- `"what should i pack for iceland in winter?"`

---

## Booking flow

Bookings are placed through the same `/chat` endpoint. The graph runs a
three-step conversational workflow rather than asking for an ID upfront:

1. **Search** — say what you want ("hotels in Bangkok", "flights SIN to
   KUL"). The agent returns the matching options as structured cards.
2. **Pick + fill** — click **Book** on a card (or type "book flight
   \<id\>"). The agent asks only for the missing details (passenger name,
   email, dates, room type, etc.). The React UI renders this as an inline
   form with prefilled known fields.
3. **Review + confirm** — once all details are known, a review card lists
   the whole booking with a **Confirm & book** button. Nothing is placed
   until the user confirms.

Behind the scenes: `sub_action=book` triggers slot-filling; a hidden
`confirm_booking=true` flag (set only when the user explicitly says "yes"
or clicks Confirm & book) unlocks the `book_hotel` / `book_flight` MCP
call.

---

## How the MCP layer works (viva notes)

**How a server exposes a tool.** Each MCP server is a `FastMCP(...)`
instance. Decorating a Python function with `@mcp.tool()` registers it —
the signature (types + docstring) becomes the tool schema clients see.
Running `mcp.run(transport="streamable-http")` starts an HTTP server that
speaks the MCP protocol. The server never knows what LLM or agent will
call it — that's the point.

**How the agents discover tools.** `MultiServerMCPClient` opens a
`streamable_http` session to each configured server, calls
`ListToolsRequest`, and returns LangChain `BaseTool` instances. We cache
that catalog on startup (`prime_mcp_tools`) so a call is one round-trip.

**How the bridge keeps external services decoupled.** Adding a Booking.com
integration means writing `mcp_servers/booking_service.py`, adding one
row to `MCP_SERVERS`, and… nothing else. No file in `agents/` needs to
change. `agents/tools.py` may gain a new thin async wrapper, but the
router, nodes, prompts, and graph don't move.

**Graceful failure.** `MCPToolCallFailed` and `MCPToolUnavailable` are
caught in every node. The node returns a friendly user message and sets
`tool_status="failed"` so the trace surfaces `FAILED` per the SRS
lifecycle. The other agents keep working — kill the flight MCP process
mid-conversation and hotels, general Q&A, and the review-and-confirm gate
are all still usable.

**Streaming.** `graph.astream_events(version="v2")` yields both
`on_chain_end` events (per node) and `on_chat_model_stream` events (per
LLM token). We forward both over SSE — the frontend renders the trace
tick-by-tick and the response types itself out.

---

## Deployment

The stack splits naturally into two hosts.

### Backend + MCP servers → Render (Docker)

The repo ships with a `Dockerfile` that runs `python main.py` in one
container. The FastAPI process spawns both MCP subprocesses on startup and
tears them down on shutdown — so one deployable, three processes.

Two paths:

**Blueprint (recommended).** Push this repo to GitHub, then in Render:
`New → Blueprint`, point at the repo. Render reads `render.yaml` and
provisions the service. Set `OPENAI_API_KEY` in the dashboard.

**Manual.** `New → Web Service → Docker`. Set:
- Runtime: Docker
- Dockerfile path: `./Dockerfile`
- Environment variables: `OPENAI_API_KEY` (required)

Render sets `$PORT` automatically; `main.py` honours it.

### Frontend → Vercel

`frontend/vercel.json` is preconfigured for Vite + client-side routing.

```bash
cd frontend
vercel                # first time; follow the prompts
vercel --prod         # promote to production
```

Set one environment variable in the Vercel dashboard:

- `VITE_API_URL` — the Render backend URL + `/chat`, e.g.
  `https://tripweaver-backend.onrender.com/chat`

The frontend uses `${VITE_API_URL}` as the `/chat` endpoint and
`${VITE_API_URL}/stream` for the SSE stream.

### Local one-shot deploy check

To sanity-check the Docker image before pushing:

```bash
docker build -t tripweaver .
docker run -p 8000:8000 -e OPENAI_API_KEY=$OPENAI_API_KEY tripweaver
# In another terminal:
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"flights from SIN to KUL"}'
```

---

## Tech stack

**Backend**
- **FastAPI** + **Uvicorn** — web framework + ASGI server
- **LangChain** / **LangGraph** — multi-agent orchestration
- **MCP** (`mcp`, `fastmcp`, `langchain-mcp-adapters`) — the tool bridge
- **OpenAI** — `gpt-4o-mini` for router and general Q&A
- **python-dotenv** — env-var loader

**Frontend**
- **React 19** + **Vite** + **TypeScript**
- **Tailwind CSS v4** — theming
- **Motion** — animations
- **liquid-glass** — refractive glass surfaces on hero cards
