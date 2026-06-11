import logging
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile

from app.application.services.knowledge_service import KnowledgeService
from app.domain.models.knowledge_base import KnowledgeBase
from app.domain.models.knowledge_file import KnowledgeFile
from app.interfaces.auth_dependencies import CurrentUser, get_current_user
from app.interfaces.schemas import Response
from app.interfaces.schemas.knowledge import CreateKnowledgeBaseRequest
from app.interfaces.service_dependencies import get_knowledge_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/knowledge-bases", tags=["知识库模块"])


@router.post(path="", response_model=Response[KnowledgeBase], summary="新建知识库")
async def create_knowledge_base(
        body: CreateKnowledgeBaseRequest,
        current_user: CurrentUser = Depends(get_current_user),
        service: KnowledgeService = Depends(get_knowledge_service),
) -> Response[KnowledgeBase]:
    """在当前租户下新建知识库"""
    kb = await service.create_knowledge_base(
        tenant_id=current_user.tenant_id, owner_id=current_user.user_id,
        name=body.name, description=body.description,
    )
    return Response.success(msg="新建知识库成功", data=kb)


@router.get(path="", response_model=Response[List[KnowledgeBase]], summary="知识库列表")
async def list_knowledge_bases(
        current_user: CurrentUser = Depends(get_current_user),
        service: KnowledgeService = Depends(get_knowledge_service),
) -> Response[List[KnowledgeBase]]:
    """列出当前租户的全部知识库"""
    kbs = await service.list_knowledge_bases(current_user.tenant_id)
    return Response.success(msg="获取知识库列表成功", data=kbs)


@router.get(path="/{kb_id}", response_model=Response[KnowledgeBase], summary="知识库详情")
async def get_knowledge_base(
        kb_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        service: KnowledgeService = Depends(get_knowledge_service),
) -> Response[KnowledgeBase]:
    """获取知识库详情(校验租户归属)"""
    kb = await service.get_knowledge_base(kb_id, current_user.tenant_id)
    return Response.success(msg="获取知识库成功", data=kb)


@router.delete(path="/{kb_id}", response_model=Response[None], summary="删除知识库")
async def delete_knowledge_base(
        kb_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        service: KnowledgeService = Depends(get_knowledge_service),
) -> Response[None]:
    """删除知识库(级联删除文件与切片)"""
    await service.delete_knowledge_base(kb_id, current_user.tenant_id)
    return Response.success(msg="删除知识库成功", data=None)


@router.post(path="/{kb_id}/files", response_model=Response[KnowledgeFile], summary="上传文件到知识库")
async def upload_knowledge_file(
        kb_id: str,
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        current_user: CurrentUser = Depends(get_current_user),
        service: KnowledgeService = Depends(get_knowledge_service),
) -> Response[KnowledgeFile]:
    """上传文件到知识库，解析/向量化/入库在后台异步进行(经 FileStatus 跟踪进度)"""
    kf = await service.upload_file(
        kb_id=kb_id, tenant_id=current_user.tenant_id,
        owner_id=current_user.user_id, upload_file=file,
    )
    # 后台执行入库流水线(再下载/解析/分块/向量化/落库)
    background_tasks.add_task(service.ingest_file, kf.id, current_user.tenant_id)
    return Response.success(msg="上传成功，正在后台解析入库", data=kf)


@router.get(path="/{kb_id}/files", response_model=Response[List[KnowledgeFile]], summary="知识库文件列表")
async def list_knowledge_files(
        kb_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        service: KnowledgeService = Depends(get_knowledge_service),
) -> Response[List[KnowledgeFile]]:
    """列出知识库下的文件及其处理状态"""
    files = await service.list_files(kb_id, current_user.tenant_id)
    return Response.success(msg="获取文件列表成功", data=files)
