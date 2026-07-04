from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import uuid
import time

app = FastAPI()

# ---------------- CORS ----------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- CONFIG ----------------

TOTAL_ORDERS = 51
RATE_LIMIT = 20
WINDOW = 10  # seconds

# ---------------- DATA ----------------

catalog = [{"id": i} for i in range(1, TOTAL_ORDERS + 1)]

idempotency_store = {}

client_requests = {}


# ---------------- MODELS ----------------

class OrderRequest(BaseModel):
    item: Optional[str] = None
    quantity: Optional[int] = 1


# ---------------- RATE LIMIT ----------------

def rate_limit(client_id: str):
    now = time.time()

    bucket = client_requests.setdefault(client_id, [])

    bucket[:] = [t for t in bucket if now - t < WINDOW]

    if len(bucket) >= RATE_LIMIT:
        retry_after = max(1, int(WINDOW - (now - bucket[0])))

        return JSONResponse(
            status_code=429,
            headers={
                "Retry-After": str(retry_after)
            },
            content={
                "detail": "Rate limit exceeded"
            }
        )

    bucket.append(now)
    return None


# ---------------- CREATE ORDER ----------------

@app.post("/orders", status_code=201)
def create_order(
    order: OrderRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    client_id: str = Header("default", alias="X-Client-Id"),
):
    rl = rate_limit(client_id)
    if rl:
        return rl

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    created = {
        "id": str(uuid.uuid4()),
        "item": order.item,
        "quantity": order.quantity,
    }

    idempotency_store[idempotency_key] = created

    return JSONResponse(
        status_code=201,
        content=created
    )


# ---------------- LIST ORDERS ----------------

@app.get("/orders")
def list_orders(
    limit: int = 10,
    cursor: Optional[str] = None,
    client_id: str = Header("default", alias="X-Client-Id"),
):
    rl = rate_limit(client_id)
    if rl:
        return rl

    try:
        start = int(cursor) if cursor else 0
    except ValueError:
        start = 0

    if start < 0:
        start = 0

    end = min(start + limit, TOTAL_ORDERS)

    items = catalog[start:end]

    next_cursor = str(end) if end < TOTAL_ORDERS else None

    return {
        "items": items,
        "next_cursor": next_cursor,
    }


@app.get("/")
def root():
    return {"status": "ok"}