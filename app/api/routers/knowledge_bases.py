from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.knowledge_base import KnowledgeBase
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseRead, KnowledgeBaseUpdate
from app.services.rag import clear_knowledge_base_index

router = APIRouter(prefix="/knowledge-bases", tags=["Knowledge bases"])


def get_knowledge_base_or_404(db: Session, knowledge_base_id: int) -> KnowledgeBase:
    knowledge_base = db.get(KnowledgeBase, knowledge_base_id)
    if knowledge_base is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")
    return knowledge_base


@router.post("", response_model=KnowledgeBaseRead, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(payload: KnowledgeBaseCreate, db: Session = Depends(get_db)) -> KnowledgeBase:
    knowledge_base = KnowledgeBase(**payload.model_dump())
    db.add(knowledge_base)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="知识库名称已存在") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="知识库保存失败") from exc
    db.refresh(knowledge_base)
    return knowledge_base


@router.get("", response_model=list[KnowledgeBaseRead])
def list_knowledge_bases(
    db: Session = Depends(get_db),
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[KnowledgeBase]:
    return db.query(KnowledgeBase).order_by(KnowledgeBase.id.desc()).offset(offset).limit(limit).all()


@router.get("/{knowledge_base_id}", response_model=KnowledgeBaseRead)
def get_knowledge_base(knowledge_base_id: int, db: Session = Depends(get_db)) -> KnowledgeBase:
    return get_knowledge_base_or_404(db, knowledge_base_id)


@router.put("/{knowledge_base_id}", response_model=KnowledgeBaseRead)
def update_knowledge_base(
    knowledge_base_id: int,
    payload: KnowledgeBaseUpdate,
    db: Session = Depends(get_db),
) -> KnowledgeBase:
    knowledge_base = get_knowledge_base_or_404(db, knowledge_base_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(knowledge_base, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="知识库名称已存在") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="知识库更新失败") from exc
    db.refresh(knowledge_base)
    return knowledge_base


@router.delete("/{knowledge_base_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_base(
    knowledge_base_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    knowledge_base = get_knowledge_base_or_404(db, knowledge_base_id)
    db.delete(knowledge_base)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="知识库删除失败") from exc
    try:
        clear_knowledge_base_index(knowledge_base_id, getattr(request.app.state, "vector_store", None))
    except Exception:
        pass
    return Response(status_code=status.HTTP_204_NO_CONTENT)
