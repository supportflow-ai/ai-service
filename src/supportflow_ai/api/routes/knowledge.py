from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator
from starlette.concurrency import run_in_threadpool

from supportflow_ai.api.dependencies import authorize_service
from supportflow_ai.domain.knowledge import InvalidIndexRequestError

router = APIRouter(tags=["knowledge"])


class IndexRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=False)

    request_id: UUID = Field(alias="requestId")
    article_id: UUID = Field(alias="articleId")
    article_version_id: UUID = Field(alias="articleVersionId")
    version_number: StrictInt = Field(alias="versionNumber", ge=1)
    source_hash: str = Field(alias="sourceHash", pattern=r"^[0-9a-f]{64}$")
    profile_id: str = Field(alias="profileId", min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=131_072)

    @field_validator("title", "content")
    @classmethod
    def valid_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("blank_text")
        value.encode("utf-8", errors="strict")
        return value


@router.post("/v1/knowledge-indexes:prepare", dependencies=[Depends(authorize_service)])
async def prepare_index(payload: IndexRequest, request: Request):
    preparer = request.app.state.prepare_knowledge_index
    if preparer is None:
        raise HTTPException(503, detail={"code": "embedding_provider_unavailable"})
    try:
        return await run_in_threadpool(preparer.execute, **payload.model_dump())
    except InvalidIndexRequestError as exc:
        raise HTTPException(400, detail={"code": "invalid_index_snapshot"}) from exc
