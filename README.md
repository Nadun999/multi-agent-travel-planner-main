# Booking Agents Backend

A FastAPI-based booking system with hotel and flight agents powered by LangChain.

## Structure

```
backend/
├── req/
│   └── requirements.txt    # Python dependencies
├── agents/
│   ├── hotel_agent.py     # Hotel booking agent
│   ├── flight_agent.py    # Flight booking agent
│   ├── orchestrator.py    # Routes queries to correct agent
│   └── __init__.py
├── app/
│   └── main.py           # FastAPI app with endpoints
├── llm.py              # LangChain ChatOpenAI
├── config.py           # Config loader
└── .env              # Environment variables
```

## Setup

### 1. Install Dependencies
```bash
cd backend/req
pip install -r requirements.txt
```

### 2. Configure API Key
Edit `.env` and add your OpenAI API key:
```
OPENAI_API_KEY=your_actual_api_key_here
```

### 3. Run the Server
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

## API Endpoints

| Endpoint | Method | Description | Example |
|----------|--------|-------------|---------|
| `/hotels` | GET | Get all hotels | `curl http://localhost:8000/hotels` |
| `/flights` | GET | Get all flights | `curl http://localhost:8000/flights` |
| `/chat` | POST | Chat with agent | See below |

### Chat Example

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "find me a hotel in NYC"}'
```

**Other queries to try:**
- "show me all hotels"
- "find flights from New York to London"
- "show all flights"

## Booking

The agent can book hotels and flights through the same `/chat` endpoint.
First search for options — each result carries an `_id` (shown on the
cards in the React UI, where you can click to copy it). Then reference
that id in a booking request and include the required details.

**Book a hotel** — needs `hotel_id`, `guest_name`, `guest_email`,
`room_type`, `check_in`, and `check_out`:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "book hotel H123 for John Doe (john.doe@example.com), suite, from 2026-06-01 to 2026-06-05"}'
```

**Book a flight** — needs `flight_id`, `passenger_name`, and
`passenger_email`:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "book flight F456 for Jane Smith with email jane.smith@example.com"}'
```

If any required field is missing, the agent replies asking for the
specific details it still needs.

### Conversation context

The backend keeps the recent conversation history and threads it into
the prompt, so follow-up messages work without repeating everything —
e.g. search flights, then say "book the first one for Jane
(jane@example.com)".

## React Chat UI

A React + Vite chat interface lives in `frontend/`.

Run the FastAPI backend first:

```bash
python main.py
```

Then start the frontend dev server:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL shown in the terminal (default `http://localhost:5173`).
Set `VITE_API_URL` to point at a non-default backend, e.g.
`VITE_API_URL=http://127.0.0.1:8000/chat npm run dev`.

## Tech Stack

**Backend**
- **FastAPI** - Web framework
- **LangChain / LangGraph** - Agent framework
- **OpenAI** - LLM (GPT-4o-mini)
- **python-dotenv** - Environment config

**Frontend**
- **React + Vite + TypeScript**
- **Tailwind CSS** - Styling
- **Motion** - Animations