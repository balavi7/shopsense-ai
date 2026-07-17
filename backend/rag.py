import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"

import json
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────────────
KNOWLEDGE_BASE_DIR = Path(__file__).parent.parent / "knowledge_base"
CHROMA_PERSIST_DIR = Path(__file__).parent.parent / "chroma_store"
COLLECTION_NAME = "shopsense_kb"

# Embedding model — runs fully locally via sentence-transformers, no API key needed
# Install: pip install sentence-transformers
# Downloads ~90MB on first run, cached locally after that
EMBED_MODEL = "all-MiniLM-L6-v2"


# ── ChromaDB client (persistent) ───────────────────────────────────────────
def get_chroma_client():
    return chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))


def get_embedding_function():
    """
    Uses all-MiniLM-L6-v2 via sentence-transformers.
    Runs entirely on your local machine — no API key, no internet after first download.
    This is the production embedding function for ShopSense AI.
    """
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBED_MODEL
    )


# ── Chunker ────────────────────────────────────────────────────────────────
def chunk_markdown(text: str, source: str, chunk_size: int = 300) -> list[dict]:
    """
    Split markdown text into overlapping chunks.
    Each chunk carries metadata so we know which doc it came from.
    """
    words = text.split()
    chunks = []
    overlap = 50

    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append({
                "text": chunk,
                "source": source,
                "chunk_index": len(chunks)
            })

    return chunks


def chunk_orders(orders: list[dict]) -> list[dict]:
    """
    Convert each mock order into a natural language string and treat it as a chunk.
    This lets the agent answer questions like 'what is the status of order SS10002'.
    """
    chunks = []
    for order in orders:
        parts = [
            f"Order ID: {order['order_id']}",
            f"Customer: {order['customer_name']}",
            f"Product: {order['product']}",
            f"Quantity: {order['quantity']}",
            f"Price: ₹{order['price']}",
            f"Payment Method: {order['payment_method']}",
            f"Order Date: {order['order_date']}",
            f"Status: {order['status']}",
        ]

        # Append optional fields only if they exist
        optional_fields = [
            ("delivery_date", "Delivered On"),
            ("expected_delivery", "Expected Delivery"),
            ("tracking_id", "Tracking ID"),
            ("return_reason", "Return Reason"),
            ("return_initiated_date", "Return Initiated On"),
            ("refund_status", "Refund Status"),
            ("refund_amount", "Refund Amount"),
            ("refund_date", "Refund Date"),
            ("refund_initiated_date", "Refund Initiated On"),
            ("refund_expected_by", "Refund Expected By"),
            ("cancellation_reason", "Cancellation Reason"),
        ]

        for key, label in optional_fields:
            if order.get(key):
                val = order[key]
                if key == "refund_amount":
                    val = f"₹{val}"
                parts.append(f"{label}: {val}")

        chunks.append({
            "text": ". ".join(parts),
            "source": "mock_orders.json",
            "chunk_index": len(chunks),
            "order_id": order["order_id"]
        })

    return chunks


# ── Ingest knowledge base into ChromaDB ───────────────────────────────────
def ingest_knowledge_base(force: bool = False):
    """
    Load all documents from knowledge_base/, chunk them,
    and upsert into ChromaDB. Set force=True to re-ingest from scratch.
    """
    client = get_chroma_client()
    embed_fn = get_embedding_function()

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"}
    )

    # Skip if already ingested and not forcing
    if collection.count() > 0 and not force:
        print(f"[RAG] Collection already has {collection.count()} chunks. Skipping ingest.")
        return collection

    if force and collection.count() > 0:
        print("[RAG] Force re-ingest — deleting existing collection...")
        client.delete_collection(COLLECTION_NAME)
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=embed_fn,
            metadata={"hnsw:space": "cosine"}
        )

    print("[RAG] Starting knowledge base ingestion...")

    all_chunks = []

    # 1. Markdown files
    for md_file in sorted(KNOWLEDGE_BASE_DIR.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        chunks = chunk_markdown(text, source=md_file.name)
        all_chunks.extend(chunks)
        print(f"[RAG] Chunked {md_file.name} → {len(chunks)} chunks")

    # 2. Orders JSON
    orders_file = KNOWLEDGE_BASE_DIR / "mock_orders.json"
    if orders_file.exists():
        orders = json.loads(orders_file.read_text(encoding="utf-8"))
        order_chunks = chunk_orders(orders)
        all_chunks.extend(order_chunks)
        print(f"[RAG] Chunked mock_orders.json → {len(order_chunks)} chunks")

    # Upsert into ChromaDB
    if all_chunks:
        documents = [c["text"] for c in all_chunks]
        ids = [f"chunk_{i}" for i in range(len(all_chunks))]
        metadatas = [{"source": c["source"], "chunk_index": c["chunk_index"]} for c in all_chunks]

        collection.upsert(documents=documents, ids=ids, metadatas=metadatas)
        print(f"[RAG] Ingestion complete. Total chunks in store: {collection.count()}")
    else:
        print("[RAG] ⚠️  No chunks found. Check your knowledge_base/ folder.")

# ── Query ChromaDB ─────────────────────────────────────────────────────────
def retrieve_context(query: str, n_results: int = 4) -> dict:
    """
    Given a user query, retrieve the top-N most relevant chunks from ChromaDB.
    Returns context text, sources, similarity score, and a confidence flag.

    confidence threshold: similarity >= 0.4 is considered a confident retrieval.
    If confident=False, the FastAPI layer logs it as an unanswered query for
    knowledge base improvement — this is the FDE feedback loop.
    """
    client = get_chroma_client()
    embed_fn = get_embedding_function()

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"}
    )

    if collection.count() == 0:
        print("[RAG] Collection is empty. Running ingestion first...")
        ingest_knowledge_base()

    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, collection.count()),
        include=["documents", "metadatas", "distances"]
    )

    docs = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    # Cosine distance → similarity (lower distance = higher similarity)
    top_score = 1 - distances[0] if distances else 0

    context_blocks = []
    for doc, meta, dist in zip(docs, metadatas, distances):
        similarity = round(1 - dist, 4)
        context_blocks.append({
            "text": doc,
            "source": meta.get("source", "unknown"),
            "similarity": similarity
        })

    # Confidence threshold — below this, query gets logged as unanswered
    confident = top_score >= 0.4

    return {
        "context": "\n\n".join([cb["text"] for cb in context_blocks]),
        "sources": [cb["source"] for cb in context_blocks],
        "top_similarity": round(top_score, 4),
        "confident": confident,
        "blocks": context_blocks
    }


# ── Quick test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ingest_knowledge_base(force=True)

    test_queries = [
        "What is the status of order SS10002?",
        "How long does a refund take for credit card payments?",
        "Can I cancel my order after it has been dispatched?",
        "My item was damaged, what should I do?",
    ]

    print("\n─── Retrieval Test ───\n")
    for q in test_queries:
        result = retrieve_context(q)
        print(f"Q: {q}")
        print(f"   Confident: {result['confident']} | Top similarity: {result['top_similarity']}")
        print(f"   Sources: {set(result['sources'])}")
        print(f"   Context preview: {result['context'][:200]}...")
        print()
