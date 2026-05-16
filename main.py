from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from entity import ChatRequest, ChatResponse
from agents.tools import get_hotels, get_flights
from agents.graph import graph


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    initial_state = {
        "messages": [request.message],
        "intent": "",
        "sub_action": "",
        "hotel_results": [],
        "flight_results": [],
        "response_text": "",
    }

    result = graph.invoke(initial_state)

    return ChatResponse(
        response=result.get("response_text", "Something went wrong. Please try again."),
        hotels=result.get("hotel_results", []) or None,
        flights=result.get("flight_results", []) or None,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)