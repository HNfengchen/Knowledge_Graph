from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from kg_system.api.deps import require_user
from kg_system.core.exceptions import NotImplementedInSkeleton
from kg_system.core.models import ApiResponse, SubgraphResult

router = APIRouter(prefix="/reason", tags=["reason"])


class AskRequest(BaseModel):
    question: str
    max_steps: int = Field(5, ge=1, le=20)


class AskResponse(BaseModel):
    answer: str
    reasoning_trace: list[str]
    evidence: SubgraphResult


@router.post("/ask", response_model=ApiResponse[AskResponse])
async def ask_endpoint(body: AskRequest, user=Depends(require_user)):
    raise NotImplementedInSkeleton()
