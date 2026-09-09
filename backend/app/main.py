from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Deterministic Support Agent API",
    description="Reliable multi-step customer support agent powered by LangGraph",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "message": "Deterministic Support Agent API is running",
        "version": "0.1.0",
        "framework": "LangGraph"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}

# Future: /chat endpoint that invokes the LangGraph agent
