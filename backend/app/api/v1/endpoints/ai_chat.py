from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.ai_assistant import AIAssistantService

router = APIRouter()

class AIChatRequest(BaseModel):
    query: str
    report_context: Dict[str, Any] = {}

class AIChatResponse(BaseModel):
    response: str

@router.post("/chat", response_model=AIChatResponse)
async def chat_with_analyst(payload: AIChatRequest):
    """
    Context-aware financial AI assistant answering questions about the active report.
    """
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Savol matni bo'sh bo'lishi mumkin emas")

    answer = await AIAssistantService.answer_query(
        query=payload.query,
        context_data=payload.report_context
    )
    return AIChatResponse(response=answer)
