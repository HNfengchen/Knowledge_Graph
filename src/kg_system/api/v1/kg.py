from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field

from kg_system.api.deps import get_kg_query, get_neo4j, get_redis, require_user
from kg_system.builder.pdf_processor import PdfProcessor
from kg_system.builder.pipeline import KGBuildPipeline
from kg_system.core.config import get_settings
from kg_system.core.models import ApiResponse, IngestResponse, PdfResult, SubgraphResult
from kg_system.kg_query.service import KGQueryService
from kg_system.llm.callbacks import AnalysisCallbackHandler
from kg_system.llm.factory import get_chat_model
from kg_system.storage.neo4j_client import Neo4jClient
from kg_system.storage.redis_client import RedisClient

router = APIRouter(prefix="/kg", tags=["kg"])


class BuildRequest(BaseModel):
    text: str = Field(..., min_length=1)
    doc_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BuildResponseData(BaseModel):
    doc_id: str
    chunks: int
    entities_upserted: int
    relations_upserted: int


class QueryRequest(BaseModel):
    entity_name: str
    depth: int = Field(2, ge=1, le=3)
    relation_types: list[str] | None = None


@router.post("/build", response_model=ApiResponse[BuildResponseData])
async def build_endpoint(
    body: BuildRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    redis: RedisClient = Depends(get_redis),
    user=Depends(require_user),
):
    s = get_settings()
    if len(body.text) > s.TEXT_MAX_LENGTH:
        from kg_system.core.exceptions import InvalidInput

        raise InvalidInput(f"text exceeds TEXT_MAX_LENGTH={s.TEXT_MAX_LENGTH}")

    callback = AnalysisCallbackHandler(redis)
    llm = get_chat_model().with_config({"callbacks": [callback]})
    pipeline = KGBuildPipeline(llm=llm, neo4j=neo4j)
    doc_id = body.doc_id or KGBuildPipeline.gen_doc_id()
    result = await pipeline.run(body.text, doc_id)
    return ApiResponse(
        data=BuildResponseData(
            doc_id=result.doc_id,
            chunks=result.chunks,
            entities_upserted=result.entities_upserted,
            relations_upserted=result.relations_upserted,
        )
    )


@router.post("/ingest-pdf", response_model=ApiResponse[IngestResponse])
async def ingest_pdf(
    file: UploadFile = File(...),
    doc_id: str | None = Form(None),
    neo4j: Neo4jClient = Depends(get_neo4j),
    redis: RedisClient = Depends(get_redis),
    user=Depends(require_user),
):
    s = get_settings()

    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in s.SUPPORTED_FILE_EXTENSIONS:
        from kg_system.core.exceptions import InvalidInput
        raise InvalidInput(f"unsupported file type '{ext}', supported: {s.SUPPORTED_FILE_EXTENSIONS}")

    data = await file.read()
    if len(data) > s.MAX_FILE_SIZE:
        from kg_system.core.exceptions import InvalidInput
        raise InvalidInput(f"file too large, max {s.MAX_FILE_SIZE // (1024*1024)}MB")

    actual_doc_id = doc_id or Path(file.filename).stem

    processor = PdfProcessor(ocr_lang=s.OCR_LANGUAGE)
    pdf_result = processor.process_pdf(data)

    if not pdf_result.text.strip():
        return ApiResponse(
            data=IngestResponse(
                doc_id=actual_doc_id,
                page_count=pdf_result.page_count,
                chunks=0,
                entities_upserted=0,
                relations_upserted=0,
            )
        )

    callback = AnalysisCallbackHandler(redis)
    llm = get_chat_model().with_config({"callbacks": [callback]})
    pipeline = KGBuildPipeline(llm, neo4j)

    try:
        build_result = await asyncio.wait_for(
            pipeline.run(pdf_result.text, actual_doc_id),
            timeout=s.OPENAI_TIMEOUT,
        )
    except asyncio.TimeoutError:
        from kg_system.core.exceptions import LLMTimeoutError
        raise LLMTimeoutError("PDF processing timed out")

    return ApiResponse(
        data=IngestResponse(
            doc_id=actual_doc_id,
            page_count=pdf_result.page_count,
            chunks=build_result.chunks,
            entities_upserted=build_result.entities_upserted,
            relations_upserted=build_result.relations_upserted,
        )
    )


@router.post("/query", response_model=ApiResponse[SubgraphResult])
async def query_endpoint(
    body: QueryRequest,
    kg: KGQueryService = Depends(get_kg_query),
    user=Depends(require_user),
):
    sg = await kg.query_subgraph(body.entity_name, body.depth, body.relation_types)
    return ApiResponse(data=sg)
