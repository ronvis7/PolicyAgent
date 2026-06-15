from fastapi import APIRouter

from . import status_routes,app_config_routes,file_routes,session_routes,auth_routes,knowledge_routes,tenant_llm_routes,membership_routes,enterprise_profile_routes,policy_routes,feed_routes

def create_api_routes() -> APIRouter:
    """创建API路由,涵盖整个项目的所有路由管路"""
    # 1.创建APIRouter实例
    api_router = APIRouter()

    # 2.将各个模块添加到api_router中
    api_router.include_router(auth_routes.router)
    api_router.include_router(status_routes.router)
    api_router.include_router(app_config_routes.router)
    api_router.include_router(tenant_llm_routes.router)
    api_router.include_router(membership_routes.router)
    api_router.include_router(enterprise_profile_routes.router)
    api_router.include_router(file_routes.router)
    api_router.include_router(session_routes.router)
    api_router.include_router(knowledge_routes.router)
    api_router.include_router(policy_routes.router)
    api_router.include_router(feed_routes.router)
    # 3.返回api_router实例
    return api_router

router = create_api_routes()