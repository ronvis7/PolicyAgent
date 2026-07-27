"""飞书应用机器人事件与卡片交互回调（无需 PolicyAgent 登录态）。"""

import hmac
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.domain.models.feed_item import FeedStatus
from app.infrastructure.external.notify.feishu_webhook import update_app_card_ignored
from app.infrastructure.storage.postgres import get_uow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrations/feishu", tags=["飞书集成"])


async def _resolve_tenant(body: dict):
    header = body.get("header", {})
    app_id = header.get("app_id") or body.get("app_id", "")
    token = header.get("token") or body.get("token", "")
    async with get_uow() as uow:
        settings_list = await uow.tenant_settings.list_feishu_configured()
    for settings in settings_list:
        config = settings.feishu_config
        if (
            config
            and config.app_enabled
            and config.app_id == app_id
            and hmac.compare_digest(config.verification_token, token)
        ):
            return settings.tenant_id, config
    raise HTTPException(status_code=401, detail="无效的飞书应用回调")


@router.post("/events")
async def handle_feishu_event(request: Request) -> dict:
    body = await request.json()
    if "encrypt" in body:
        raise HTTPException(status_code=400, detail="当前请勿启用飞书 Encrypt Key")
    if body.get("type") == "url_verification" or "challenge" in body:
        await _resolve_tenant(body)
        return {"challenge": body.get("challenge", "")}

    tenant_id, config = await _resolve_tenant(body)
    event_type = body.get("header", {}).get("event_type", "")
    event = body.get("event", {})
    chat_id = event.get("chat_id") or event.get("chat", {}).get("chat_id", "")
    if event_type == "im.chat.member.bot.added_v1" and chat_id:
        config = config.model_copy(update={"chat_id": chat_id})
    elif event_type == "im.chat.member.bot.deleted_v1" and chat_id == config.chat_id:
        config = config.model_copy(update={"chat_id": ""})
    else:
        return {}

    async with get_uow() as uow:
        settings = await uow.tenant_settings.get_by_tenant(tenant_id)
        if settings:
            await uow.tenant_settings.save(settings.model_copy(update={
                "feishu_config": config,
                "updated_at": datetime.now(),
            }))
    return {}


@router.post("/card-actions")
async def handle_feishu_card_action(
    request: Request, background_tasks: BackgroundTasks,
) -> dict:
    body = await request.json()
    if "encrypt" in body:
        raise HTTPException(status_code=400, detail="当前请勿启用飞书 Encrypt Key")
    tenant_id, config = await _resolve_tenant(body)
    event = body.get("event", {})
    callback_chat_id = event.get("context", {}).get("open_chat_id", "")
    if config.chat_id and callback_chat_id and callback_chat_id != config.chat_id:
        raise HTTPException(status_code=403, detail="该卡片不属于当前配置的飞书群")
    value = event.get("action", {}).get("value", {})
    if value.get("action") != "ignore_contest":
        return {"toast": {"type": "warning", "content": "暂不支持此操作"}}
    item_id = value.get("feed_item_id", "")
    if not item_id:
        raise HTTPException(status_code=400, detail="缺少 Feed 条目标识")

    async with get_uow() as uow:
        item = await uow.feed.get_by_id(tenant_id, item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="赛事提醒不存在")
        await uow.feed.save(item.model_copy(update={
            "status": FeedStatus.IGNORED,
            "updated_at": datetime.now(),
        }))

    message_id = event.get("context", {}).get("open_message_id", "")
    if message_id:
        background_tasks.add_task(update_app_card_ignored, config, message_id, item_id)
    return {"toast": {"type": "success", "content": "已忽略该赛事，后续不再提醒"}}
