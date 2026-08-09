from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.routers.knowledge_bases import get_knowledge_base_or_404
from app.db.session import get_db
from app.models.chat_message import ChatMessage
from app.schemas.chat_message import ChatMessageCreate, ChatMessageRead

router = APIRouter(prefix="/chat-messages", tags=["Chat messages"])


def get_chat_message_or_404(db: Session, chat_message_id: int) -> ChatMessage:
    chat_message = db.get(ChatMessage, chat_message_id)
    if chat_message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="问答记录不存在")
    return chat_message


@router.post("", response_model=ChatMessageRead, status_code=status.HTTP_201_CREATED)
def create_chat_message(payload: ChatMessageCreate, db: Session = Depends(get_db)) -> ChatMessage:
    get_knowledge_base_or_404(db, payload.knowledge_base_id)
    values = payload.model_dump()
    values["role"] = values["role"].value
    chat_message = ChatMessage(**values)
    db.add(chat_message)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="问答记录保存失败") from exc
    db.refresh(chat_message)
    return chat_message


@router.get("", response_model=list[ChatMessageRead])
def list_chat_messages(
    db: Session = Depends(get_db),
    knowledge_base_id: Annotated[int | None, Query(ge=1)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[ChatMessage]:
    query = db.query(ChatMessage)
    if knowledge_base_id is not None:
        query = query.filter(ChatMessage.knowledge_base_id == knowledge_base_id)
    return query.order_by(ChatMessage.id.asc()).offset(offset).limit(limit).all()


@router.get("/{chat_message_id}", response_model=ChatMessageRead)
def get_chat_message(chat_message_id: int, db: Session = Depends(get_db)) -> ChatMessage:
    return get_chat_message_or_404(db, chat_message_id)


@router.delete("/{chat_message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat_message(chat_message_id: int, db: Session = Depends(get_db)) -> Response:
    chat_message = get_chat_message_or_404(db, chat_message_id)
    db.delete(chat_message)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="问答记录删除失败") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
