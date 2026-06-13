#!/usr/bin/env bash
# 远程服务器端的 PostgreSQL 定时备份脚本。
# 部署到服务器 /opt/policy-postgres/backup.sh，由 cron 每天调用。
# 在容器内 pg_dump（自定义压缩格式）到 /opt/policy-postgres/backups，保留最近 7 天。
set -euo pipefail

COMPOSE_DIR=/opt/policy-postgres
CONTAINER=policy-postgres
BACKUP_DIR="$COMPOSE_DIR/backups"
KEEP_DAYS=7

# 读取库名/用户/密码（密码不落到命令行，避免出现在进程列表）
set -a
# shellcheck disable=SC1091
. "$COMPOSE_DIR/.env"
set +a

mkdir -p "$BACKUP_DIR"
STAMP=$(date +%Y%m%d_%H%M%S)
TARGET="$BACKUP_DIR/${POSTGRES_DB}_${STAMP}.dump"
TMP="$TARGET.partial"

# 在容器内导出，二进制经 stdout 写到宿主机临时文件；成功后再原子改名
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$CONTAINER" \
  pg_dump -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$TMP"
mv "$TMP" "$TARGET"

# 轮转：删除 7 天前的快照
find "$BACKUP_DIR" -name "${POSTGRES_DB}_*.dump" -mtime "+$KEEP_DAYS" -delete

echo "$(date '+%F %T') backup OK -> $TARGET ($(du -h "$TARGET" | cut -f1))"
