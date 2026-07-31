"""FastAPI application - health, product fetch, chat, streaming chat (PRD 21)."""
from __future__ import annotations

import json

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from . import chat_service
from .config import get_settings
from .context import sessions
from .intelligence import llm_client
from .models import AppError, ChatRequest, FetchRequest
from .navigation import parse_and_validate
from .ingestion import ingest_product
from .utilities import strip_dashes
from .utilities.logging import configure, get_logger

configure()
log = get_logger("api")
settings = get_settings()

app = FastAPI(title="Healf Product Intelligence Agent", version="1.0.0")

# FRONTEND_ORIGIN may be a single origin, a comma-separated list, or "*" (demo).
_origin = settings.frontend_origin.strip()
_allowed = ["*"] if _origin == "*" else [o.strip() for o in _origin.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

MAX_MESSAGE_LEN = 4000


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.message})


@app.get("/")
async def root() -> dict:
    # The backend is an API; there's no UI here (that's the frontend/Vercel app).
    return {
        "service": "Healf Product Intelligence Agent API",
        "status": "ok",
        "llm_configured": llm_client.is_configured(),
        "endpoints": ["/health", "/api/products/fetch", "/api/chat", "/api/chat/stream"],
        "note": "This is the backend API. The chat UI is the frontend app.",
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "llm_configured": llm_client.is_configured()}


@app.post("/api/products/fetch")
async def fetch_product(req: FetchRequest) -> dict:
    parsed = parse_and_validate(req.url)
    product = await ingest_product(parsed)
    return {"product": strip_dashes(json.loads(product.model_dump_json()))}


@app.post("/api/chat")
async def chat(req: ChatRequest) -> JSONResponse:
    _validate_message(req.message)
    session = sessions.get_or_create(req.session_id)
    product = None
    composed = None
    async for kind, payload in chat_service.pipeline(
        session,
        req.message,
        req.product_url,
        req.history,
        req.shown_suggestions,
    ):
        if kind == "product":
            product = payload
        elif kind == "composed":
            composed = payload
    response = chat_service.build_response(session, product, composed)
    return JSONResponse(content=strip_dashes(json.loads(response.model_dump_json())))


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    _validate_message(req.message)
    session = sessions.get_or_create(req.session_id)

    async def gen():
        product = None
        composed = None
        try:
            async for kind, payload in chat_service.pipeline(
                session,
                req.message,
                req.product_url,
                req.history,
                req.shown_suggestions,
            ):
                if kind == "status":
                    yield _sse("status", payload)
                elif kind == "product":
                    product = payload
                    yield _sse("product", {"product": strip_dashes(json.loads(payload.model_dump_json()))})
                elif kind == "composed":
                    composed = payload
            # Stream the answer text as tokens for a live-typing feel.
            answer_text = composed.answer.text if composed and composed.answer else ""
            for chunk in _tokenize(strip_dashes(answer_text)):
                yield _sse("token", {"text": chunk})
            response = chat_service.build_response(session, product, composed)
            yield _sse("complete", {"response": strip_dashes(json.loads(response.model_dump_json()))})
        except AppError as e:
            yield _sse("error", {"code": e.code, "message": e.message})
        except Exception as e:  # noqa: BLE001
            log.exception("stream failed")
            yield _sse("error", {"code": "INTERNAL_ERROR", "message": "Something went wrong handling your request."})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _validate_message(message: str) -> None:
    if not message or not message.strip():
        raise AppError("INVALID_URL", "Please type a question.", 400)
    if len(message) > MAX_MESSAGE_LEN:
        raise AppError("INVALID_URL", "That message is too long.", 400)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _tokenize(text: str):
    # Emit ~word-sized chunks preserving whitespace.
    buf = ""
    for ch in text:
        buf += ch
        if ch in " \n":
            yield buf
            buf = ""
    if buf:
        yield buf
