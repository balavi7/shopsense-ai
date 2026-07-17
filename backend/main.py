import sys
from pathlib import Path

# Add backend/ directory to Python path so sibling imports work
sys.path.append(str(Path(__file__).parent))


import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rag import retrieve_context, ingest_knowledge_base
from ollama_client import generate_response, is_ollama_running
from logger import log_query, get_recent_logs, get_unanswered_queries, get_stats

# ── App init ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="ShopSense AI",
    description="RAG-based AI customer support agent for ShopSense ecommerce platform",
    version="1.0.0"
)

# Allow Streamlit frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Startup: ingest knowledge base on boot ─────────────────────────────────
@app.on_event("startup")
async def startup_event():
    print("[STARTUP] Ingesting knowledge base into ChromaDB...")
    ingest_knowledge_base(force=False)
    print("[STARTUP] Knowledge base ready.")


# ── Request / Response models ──────────────────────────────────────────────
class ChatRequest(BaseModel):
    query: str
    session_id: str = "default"   # future use: per-session chat history


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]
    top_similarity: float
    confident: bool
    response_time: float


class IngestResponse(BaseModel):
    message: str
    status: str


# ── /health ────────────────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    """
    Health check endpoint.
    Returns the status of the API and whether Ollama is reachable.
    Used by Docker Compose healthcheck and GitHub Actions deploy verification.
    """
    ollama_status = "up" if is_ollama_running() else "down"
    return {
        "api": "up",
        "ollama": ollama_status,
        "model": "llama3",
    }


# ── /chat ──────────────────────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Main chat endpoint — the FDE loop in action:
    1. Retrieve relevant context from ChromaDB (RAG)
    2. Send context + query to Ollama for answer generation
    3. Log the interaction (confident or unanswered)
    4. Return the answer to the Streamlit frontend
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    start_time = time.time()

    # Step 1: RAG retrieval
    retrieval = retrieve_context(request.query, n_results=4)

    # Step 2: LLM generation
    answer = generate_response(
        query=request.query,
        context=retrieval["context"]
    )

    response_time = round(time.time() - start_time, 2)

    # Step 3: Log interaction (FDE feedback loop)
    log_query(
        query=request.query,
        answer=answer,
        sources=retrieval["sources"],
        top_similarity=retrieval["top_similarity"],
        confident=retrieval["confident"],
        response_time=response_time
    )

    # Step 4: Return to frontend
    return ChatResponse(
        answer=answer,
        sources=list(set(retrieval["sources"])),
        top_similarity=retrieval["top_similarity"],
        confident=retrieval["confident"],
        response_time=response_time
    )


# ── /orders ────────────────────────────────────────────────────────────────
@app.get("/orders/{order_id}")
def get_order(order_id: str):
    """
    Lookup a specific order by ID using RAG retrieval.
    Useful for direct order status checks from the frontend.
    """
    query = f"What is the status and details of order {order_id.upper()}?"
    retrieval = retrieve_context(query, n_results=2)

    if not retrieval["confident"]:
        raise HTTPException(
            status_code=404,
            detail=f"Order {order_id.upper()} not found in our system."
        )

    return {
        "order_id": order_id.upper(),
        "context": retrieval["context"],
        "source": retrieval["sources"],
        "similarity": retrieval["top_similarity"]
    }


# ── /ingest ────────────────────────────────────────────────────────────────
@app.post("/ingest", response_model=IngestResponse)
def reingest_knowledge_base():
    """
    Force re-ingest the knowledge base.
    Use this after adding new documents to knowledge_base/.
    This is the FDE deployment loop — update KB without restarting the service.
    """
    try:
        ingest_knowledge_base(force=True)
        return IngestResponse(
            message="Knowledge base successfully re-ingested.",
            status="success"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


# ── /logs ──────────────────────────────────────────────────────────────────
@app.get("/logs")
def fetch_logs(limit: int = 20):
    """Return recent query logs."""
    return get_recent_logs(limit=limit)


@app.get("/logs/unanswered")
def fetch_unanswered(limit: int = 20):
    """
    Return queries where RAG confidence was below threshold.
    This is the FDE feedback loop output — shows what the KB is missing.
    """
    return get_unanswered_queries(limit=limit)


@app.get("/logs/stats")
def fetch_stats():
    """Return summary stats — total queries, confidence rate, avg response time."""
    return get_stats()
