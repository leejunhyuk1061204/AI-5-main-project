# ai/app/api/v1/routes/embedding_router.py
"""
RAG 쿼리 임베딩 API (시드와 동일한 nomic-embed-text, 768차원).
백엔드 KnowledgeService가 호출하며, db/seed_v1.sql 시드 데이터와 동일한 모델을 사용한다.
"""
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import httpx

router = APIRouter(prefix="/predict", tags=["embedding"])

OLLAMA_EMBED_URL = os.getenv("OLLAMA_EMBED_URL", "http://localhost:11434/api/embed")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
EMBED_TIMEOUT_SEC = float(os.getenv("OLLAMA_EMBED_TIMEOUT", "60"))


class EmbeddingRequest(BaseModel):
    text: str = Field(..., description="임베딩할 텍스트 (RAG 검색 쿼리 등)")


class EmbeddingResponse(BaseModel):
    embedding: list[float]
    model: str


@router.post("/embedding", response_model=EmbeddingResponse)
async def get_embedding(body: EmbeddingRequest):
    """
    Ollama nomic-embed-text로 텍스트를 768차원 벡터로 임베딩한다.
    시드 스크립트(extract_and_embed_manuals_v1.py)와 동일한 모델/차원을 사용해야
    knowledge_vectors와의 유사도 검색이 유효하다.
    """
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must be non-empty")

    payload = {"model": OLLAMA_EMBED_MODEL, "input": text}
    try:
        async with httpx.AsyncClient(timeout=EMBED_TIMEOUT_SEC) as client:
            response = await client.post(OLLAMA_EMBED_URL, json=payload)
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail=f"Ollama embedding timeout ({EMBED_TIMEOUT_SEC}s)",
        )
    except httpx.ConnectError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama not reachable: {OLLAMA_EMBED_URL}. {e!s}",
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Embedding request failed: {e!s}")

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama returned {response.status_code}: {response.text[:500]}",
        )

    data = response.json()
    embeddings = data.get("embeddings")
    if not embeddings or not isinstance(embeddings, list) or len(embeddings) == 0:
        raise HTTPException(
            status_code=502,
            detail="Ollama response missing or empty 'embeddings'",
        )

    vector = embeddings[0]
    if not isinstance(vector, list) or not all(isinstance(x, (int, float)) for x in vector):
        raise HTTPException(status_code=502, detail="Invalid embedding vector type")

    return EmbeddingResponse(
        embedding=[float(x) for x in vector],
        model=OLLAMA_EMBED_MODEL,
    )
