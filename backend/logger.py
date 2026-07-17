import sqlite3
import os
from datetime import datetime
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────
DB_PATH = Path(__file__).parent.parent / "logs" / "query_logs.db"


# ── Setup ──────────────────────────────────────────────────────────────────
def init_db():
    """
    Create the logs directory and SQLite database if they don't exist.
    Two tables:
      - query_logs  : every query with its answer and confidence score
      - unanswered  : queries where RAG confidence was below threshold (FDE feedback loop)
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS query_logs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT NOT NULL,
            query           TEXT NOT NULL,
            answer          TEXT NOT NULL,
            sources         TEXT,
            top_similarity  REAL,
            confident       INTEGER,   -- 1 = confident, 0 = low confidence
            response_time   REAL       -- seconds taken end-to-end
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS unanswered_queries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            query       TEXT NOT NULL,
            similarity  REAL
        )
    """)

    conn.commit()
    conn.close()


# ── Log a query ────────────────────────────────────────────────────────────
def log_query(
    query: str,
    answer: str,
    sources: list[str],
    top_similarity: float,
    confident: bool,
    response_time: float
):
    """
    Log every query that comes through the /chat endpoint.
    If confident=False, also insert into unanswered_queries —
    this is the FDE feedback loop: surfacing gaps in the knowledge base.
    """
    init_db()

    timestamp = datetime.utcnow().isoformat()
    sources_str = ", ".join(set(sources)) if sources else ""

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO query_logs (timestamp, query, answer, sources, top_similarity, confident, response_time)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (timestamp, query, answer, sources_str, top_similarity, int(confident), response_time))

    # FDE feedback loop — log unanswered queries separately for KB improvement
    if not confident:
        cursor.execute("""
            INSERT INTO unanswered_queries (timestamp, query, similarity)
            VALUES (?, ?, ?)
        """, (timestamp, query, top_similarity))
        print(f"[LOGGER] ⚠️  Low confidence query logged for KB review: '{query}' (similarity: {top_similarity})")

    conn.commit()
    conn.close()


# ── Fetch logs ─────────────────────────────────────────────────────────────
def get_recent_logs(limit: int = 20) -> list[dict]:
    """Return the most recent query logs."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, timestamp, query, answer, sources, top_similarity, confident, response_time
        FROM query_logs
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "timestamp": r[1],
            "query": r[2],
            "answer": r[3],
            "sources": r[4],
            "top_similarity": r[5],
            "confident": bool(r[6]),
            "response_time": r[7],
        }
        for r in rows
    ]


def get_unanswered_queries(limit: int = 20) -> list[dict]:
    """Return queries where RAG confidence was below threshold."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, timestamp, query, similarity
        FROM unanswered_queries
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "timestamp": r[1],
            "query": r[2],
            "similarity": r[3],
        }
        for r in rows
    ]


def get_stats() -> dict:
    """Return summary stats for the admin dashboard."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM query_logs")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM query_logs WHERE confident = 1")
    confident_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM unanswered_queries")
    unanswered_count = cursor.fetchone()[0]

    cursor.execute("SELECT AVG(response_time) FROM query_logs")
    avg_response_time = cursor.fetchone()[0] or 0.0

    conn.close()

    return {
        "total_queries": total,
        "confident_answers": confident_count,
        "unanswered_queries": unanswered_count,
        "confidence_rate": round((confident_count / total * 100), 1) if total > 0 else 0.0,
        "avg_response_time_seconds": round(avg_response_time, 2),
    }


# ── Quick test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    print("✅ Database initialized at:", DB_PATH)

    log_query(
        query="What is the status of order SS10002?",
        answer="Your order SS10002 is currently In Transit and expected by 2026-07-08.",
        sources=["mock_orders.json"],
        top_similarity=0.87,
        confident=True,
        response_time=1.23
    )

    log_query(
        query="Do you offer same day delivery to Pune?",
        answer="I'm sorry, I don't have enough information to answer that.",
        sources=["order_policies.md"],
        top_similarity=0.31,
        confident=False,
        response_time=0.98
    )

    print("\n📊 Stats:", get_stats())
    print("\n📋 Recent logs:", get_recent_logs(5))
    print("\n⚠️  Unanswered:", get_unanswered_queries(5))
