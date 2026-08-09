from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.routers.knowledge_bases import get_knowledge_base_or_404
from app.db.session import get_db
from app.models.document import Document
from app.schemas.document import DocumentCreate, DocumentRead, DocumentUpdate
from app.services.file_storage import delete_stored_file
from app.services.rag import clear_knowledge_base_index

router = APIRouter(prefix="/documents", tags=["Documents"])


def get_document_or_404(db: Session, document_id: int) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档信息不存在")
    return document


def document_payload_to_model_values(payload: DocumentCreate | DocumentUpdate, *, partial: bool) -> dict:
    values = payload.model_dump(exclude_unset=partial)
    for enum_field in ("source_type", "status"):
        if enum_field in values and values[enum_field] is not None:
            values[enum_field] = values[enum_field].value
    return values


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def create_document(payload: DocumentCreate, db: Session = Depends(get_db)) -> Document:
    get_knowledge_base_or_404(db, payload.knowledge_base_id)
    document = Document(**document_payload_to_model_values(payload, partial=False))
    db.add(document)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="文档信息保存失败") from exc
    db.refresh(document)
    return document


@router.get("", response_model=list[DocumentRead])
def list_documents(
    db: Session = Depends(get_db),
    knowledge_base_id: Annotated[int | None, Query(ge=1)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[Document]:
    query = db.query(Document)
    if knowledge_base_id is not None:
        query = query.filter(Document.knowledge_base_id == knowledge_base_id)
    return query.order_by(Document.id.desc()).offset(offset).limit(limit).all()


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: int, db: Session = Depends(get_db)) -> Document:
    return get_document_or_404(db, document_id)


@router.put("/{document_id}", response_model=DocumentRead)
def update_document(
    document_id: int,
    payload: DocumentUpdate,
    request: Request,
    db: Session = Depends(get_db),
) -> Document:
    document = get_document_or_404(db, document_id)
    values = document_payload_to_model_values(payload, partial=True)
    if "knowledge_base_id" in values:
        get_knowledge_base_or_404(db, values["knowledge_base_id"])
    for field, value in values.items():
        setattr(document, field, value)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="文档信息更新失败") from exc
    try:
        clear_knowledge_base_index(document.knowledge_base_id, getattr(request.app.state, "vector_store", None))
    except Exception:
        pass
    db.refresh(document)
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, request: Request, db: Session = Depends(get_db)) -> Response:
    document = get_document_or_404(db, document_id)
    storage_path = document.storage_path
    knowledge_base_id = document.knowledge_base_id
    db.delete(document)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="文档信息删除失败") from exc
    try:
        clear_knowledge_base_index(knowledge_base_id, getattr(request.app.state, "vector_store", None))
    except Exception:
        pass
    delete_stored_file(storage_path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
