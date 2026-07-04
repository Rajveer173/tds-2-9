from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import time
import uuid

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

# ---------------- STORAGE ----------------

orders = [{"id": i} for i in range(1, TOTAL_ORDERS + 1)]

idempotency_store = {}

client_requests = {}

# ---------------- MODELS ----------------

class OrderRequest(BaseModel):
    item: Optional[str] = None
    quantity: Optional[int] = 1


# ---------------- RATE LIMIT ----------------

def check_rate_limit(client_id: str, response: Response):
    now = time.time()

    timestamps = client_requests.setdefault(client_id, [])

    timestamps[:] = [t for t in timestamps if now - t < WINDOW]

    if len(timestamps) >= RATE_LIMIT:
        retry = WINDOW - (now - timestamps[0])
        response.headers["Retry-After"] = str(max(1, int(retry)))
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    timestamps.append(now)


# ---------------- CREATE ORDER ----------------

@app.post("/orders", status_code=201)
def create_order(
    request: OrderRequest,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    client_id: str = Header("default", alias="X-Client-Id")
):
    check_rate_limit(client_id, response)

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    order = {
        "id": str(uuid.uuid4()),
        "item": request.item,
        "quantity": request.quantity
    }

    idempotency_store[idempotency_key] = order

    return order


# ---------------- LIST ORDERS ----------------

@app.get("/orders")
def list_orders(
    limit: int = 10,
    cursor: Optional[str] = None,
    response: Response = None,
    client_id: str = Header("default", alias="X-Client-Id")
):
    check_rate_limit(client_id, response)

    start = int(cursor) if cursor else 0

    end = min(start + limit, TOTAL_ORDERS)

    items = orders[start:end]

    next_cursor = str(end) if end < TOTAL_ORDERS else None

    return {
        "items": items,
        "next_cursor": next_cursor
    }


@app.get("/")
def root():
    return {"status": "ok"}