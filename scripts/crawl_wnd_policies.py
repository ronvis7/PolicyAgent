"""手动触发公开政策入库（主线②）。

抓取无锡新吴区门户「政策文件」栏目，结构化 upsert 入 policies 表，并向量双写进
全局公开知识库。手动运行(定时后置)：

    cd api && python ../scripts/crawl_wnd_policies.py --max-pages 2

依赖与服务端一致(.env / config.yaml)，需数据库可连通(远程隧道或本地)。
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# 与服务端运行时一致：将 api 目录加入 import 路径并切作工作目录，
# 使 config.yaml / .env 等相对路径正确解析。
_API_DIR = Path(__file__).resolve().parents[1] / "api"
sys.path.insert(0, str(_API_DIR))
os.chdir(_API_DIR)

from app.infrastructure.storage.postgres import get_postgres  # noqa: E402
from app.interfaces.service_dependencies import get_policy_ingest_service  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("crawl_wnd_policies")


async def main(max_pages: int) -> None:
    """初始化数据库连接 → 执行入库 → 收尾"""
    await get_postgres().init()
    try:
        service = get_policy_ingest_service()
        summary = await service.ingest(max_pages=max_pages)
        logger.info(f"公开政策入库完成: {summary}")
        print(f"OK 入库完成: {summary}")
    finally:
        await get_postgres().shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="抓取无锡新吴区公开政策并入库")
    parser.add_argument("--max-pages", type=int, default=1, help="抓取的列表页数(每页约20条)")
    args = parser.parse_args()
    asyncio.run(main(args.max_pages))
