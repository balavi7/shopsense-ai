import requests
import os

# ── Config ─────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:1.5b")  # swap to mistral if preferred


# ── Health check ───────────────────────────────────────────────────────────
def is_ollama_running() -> bool:
    """Check if the Ollama server is reachable."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        return resp.status_code == 200
    except requests.exceptions.ConnectionError:
        return False


# ── Core generation ────────────────────────────────────────────────────────
def generate_response(query: str, context: str) -> str:
    """
    Send a query + retrieved context to Ollama and return the LLM's answer.

    The system prompt locks the model into being a ShopSense support agent —
    it must only answer using the provided context and never hallucinate.
    """

    system_prompt = """You are ShopSense AI, a helpful and concise customer support assistant for ShopSense, an Indian ecommerce platform.

Your job is to answer customer queries about their orders, refunds, returns, and shipping policies.

Rules you must follow:
- Answer ONLY using the context provided below. Do not make up information.
- If the context does not contain enough information to answer, say: "I'm sorry, I don't have enough information to answer that. Please contact our support team."
- Give a friendly, complete answer in 2-3 sentences
- When mentioning amounts, always use the ₹ symbol.
- When referencing order IDs, always mention them explicitly.
- Do not reveal that you are an AI model or mention Ollama, LLMs, or any technical details.
"""

    user_message = f"""Context:
{context}

Customer query: {query}

Give a friendly, complete answer in 2-3 sentences using only the context above.
Answer:"""

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": user_message,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,   # low temp = factual, consistent answers
            "num_predict": 500,   # cap response length
        }
    }

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=60
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()

    except requests.exceptions.ConnectionError:
        return "⚠️ The AI service is currently unavailable. Please try again in a moment."

    except requests.exceptions.Timeout:
        return "⚠️ The request timed out. The model may be loading — please try again."

    except Exception as e:
        return f"⚠️ An unexpected error occurred: {str(e)}"


# ── Quick test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not is_ollama_running():
        print("❌ Ollama is not running. Start it with: ollama serve")
    else:
        print("✅ Ollama is running.")
        test_context = """Order ID: SS10002. Customer: Priya Nair. Product: boAt Airdopes 141 - Black.
Status: In Transit. Expected Delivery: 2026-07-08. Tracking ID: BLUEDART112233."""
        test_query = "Where is my order SS10002?"
        print(f"\nQ: {test_query}")
        print(f"A: {generate_response(test_query, test_context)}")
