from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.routers.documents import get_document_or_404
from app.db.session import get_db
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_processing_task import DocumentProcessingTask
from app.schemas.document_processing import DocumentChunkRead, DocumentProcessingTaskRead
from app.services.document_processing import process_document_task
from app.services.file_storage import MAX_UPLOAD_SIZE_BYTES, delete_stored_file, save_upload, validate_filename
from app.services.rag import clear_knowledge_base_index

document_router = APIRouter(prefix="/documents", tags=["Document processing"])
task_router = APIRouter(prefix="/document-processing-tasks", tags=["Document processing"])


def create_processing_task(db: Session, document: Document, operation: str) -> DocumentProcessingTask:
    if document.processing_status in {"queued", "processing"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="文档正在处理中，请等待当前任务完成")

    task = DocumentProcessingTask(document_id=document.id, operation=operation, status="queued")
    document.processing_status = "queued"
    document.processing_error = None
    db.add(task)
    return task


@document_router.post("/{document_id}/upload", response_model=DocumentProcessingTaskRead, status_code=status.HTTP_202_ACCEPTED)
async def upload_document_file(
    document_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DocumentProcessingTask:
    document = get_document_or_404(db, document_id)
    try:
        validate_filename(file.filename)
        content = await file.read(MAX_UPLOAD_SIZE_BYTES + 1)
        storage_path, _ = save_upload(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="文件保存失败") from exc
    finally:
        await file.close()

    old_storage_path = document.storage_path
    document.storage_path = storage_path
    document.original_filename = (file.filename or "").replace("\\", "/").split("/")[-1][:255]
    document.file_size = len(content)
    document.processed_at = None
    task = create_processing_task(db, document, "upload")
    try:
        db.commit()
        db.refresh(task)
    except SQLAlchemyError as exc:
        db.rollback()
        delete_stored_file(storage_path)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="处理任务创建失败") from exc

    if old_storage_path and old_storage_path != storage_path:
        delete_stored_file(old_storage_path)
    try:
        clear_knowledge_base_index(document.knowledge_base_id, getattr(request.app.state, "vector_store", None))
    except Exception:
        pass
    runner = getattr(request.app.state, "document_processing_runner", process_document_task)
    background_tasks.add_task(runner, task.id)
    return task


@document_router.post("/{document_id}/reprocess", response_model=DocumentProcessingTaskRead, status_code=status.HTTP_202_ACCEPTED)
def reprocess_document(
    document_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
) -> DocumentProcessingTask:
    document = get_document_or_404(db, document_id)
    if not document.storage_path:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="文档尚未上传文件，无法重新处理")
    task = create_processing_task(db, document, "reprocess")
    try:
        db.commit()
        db.refresh(task)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="处理任务创建失败") from exc
    try:
        clear_knowledge_base_index(document.knowledge_base_id, getattr(request.app.state, "vector_store", None))
    except Exception:
        pass
    runner = getattr(request.app.state, "document_processing_runner", process_document_task)
    background_tasks.add_task(runner, task.id)
    return task


@document_router.get("/{document_id}/chunks", response_model=list[DocumentChunkRead])
def list_document_chunks(
    document_id: int,
    db: Session = Depends(get_db),
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[DocumentChunk]:
    get_document_or_404(db, document_id)
    return (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@task_router.get("", response_model=list[DocumentProcessingTaskRead])
def list_processing_tasks(
    db: Session = Depends(get_db),
    document_id: Annotated[int | None, Query(ge=1)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[DocumentProcessingTask]:
    query = db.query(DocumentProcessingTask)
    if document_id is not None:
        query = query.filter(DocumentProcessingTask.document_id == document_id)
    return query.order_by(DocumentProcessingTask.id.desc()).offset(offset).limit(limit).all()


@task_router.get("/{task_id}", response_model=DocumentProcessingTaskRead)
def get_processing_task(task_id: int, db: Session = Depends(get_db)) -> DocumentProcessingTask:
    task = db.get(DocumentProcessingTask, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档处理任务不存在")
    return task
