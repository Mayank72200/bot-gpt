from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_document_service
from app.schemas.document import DocumentResponse, DocumentUploadRequest
from app.services.document_service import DocumentService


router = APIRouter(prefix="/documents", tags=["documents"])


def _to_document_response(document, chunk_count: int) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        user_id=document.user_id,
        title=document.title,
        created_at=document.created_at,
        chunk_count=chunk_count,
    )


@router.post("", response_model=DocumentResponse)
async def upload_document(
    payload: DocumentUploadRequest,
    db: Session = Depends(get_db),
    service: DocumentService = Depends(get_document_service),
):
    document, chunk_count = await service.upload_document(db, payload.user_id, payload.title, payload.text)
    return _to_document_response(document, chunk_count)


@router.post("/upload-file", response_model=DocumentResponse)
async def upload_document_file(
    user_id: str = Form(...),
    title: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    service: DocumentService = Depends(get_document_service),
):
    file_bytes = await file.read()
    resolved_title = (title or "").strip() or Path(file.filename or "uploaded-document").stem
    text = service.extract_text_from_uploaded_file(file.filename or "uploaded-document", file_bytes)
    document, chunk_count = await service.upload_document(db, user_id, resolved_title, text)
    return _to_document_response(document, chunk_count)
