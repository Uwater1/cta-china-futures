#!/usr/bin/env bash
# 配额感知的多日续跑:反复执行 run_all.sh,直到它不再以 3(当日流量配额耗尽)退出。
# 试用账户每天 1 GiB,5 分钟线全量约需 3 天;适合挂后台无人值守。
#
# 用法(仓库根目录):
#   nohup download/continue_daily.sh >> download/run.log 2>&1 &
# 停止:kill $(pgrep -f continue_daily.sh)
set -u
cd "$(dirname "$0")/.."
while :; do
  echo "[continue] $(date '+%F %T %Z') start run_all"
  bash download/run_all.sh
  rc=$?
  if [ "$rc" != 3 ]; then
    echo "[continue] run_all exit=$rc;停止"
    exit "$rc"
  fi
  days=$(.venv/bin/python -c "import rqdatac; rqdatac.init(); print(rqdatac.user.get_quota().get('remaining_days', 99))" 2>/dev/null || echo 99)
  if [ "$days" -le 2 ] 2>/dev/null; then
    echo "[continue] license 剩余 $days 天,停止(数据未下完,请续期后重跑)"
    exit 4
  fi
  echo "[continue] 配额已满,30 分钟后重试 ($(date '+%F %T %Z'),license 剩余 $days 天)"
  sleep 1800
done
