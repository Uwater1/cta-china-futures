#!/usr/bin/env bash
# 按优先级串行下载全部米筐数据。配额(试用 1 GiB/天)不足时脚本以 3 退出,
# 第二天原样重跑即可续(已有文件会跳过)。全部脚本幂等。
#
# 用法(仓库根目录):
#   download/run_all.sh              # 日频 + 非量价 + 宏观 + 5 分钟 + 期权
#   download/run_all.sh --no-5m      # 跳过 5 分钟线(只跑轻量数据)
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
NO_5M=0
for a in "$@"; do [ "$a" = "--no-5m" ] && NO_5M=1; done

run() {
  echo "==> $*"
  "$@" || rc=$?
  rc=${rc:-0}
  if [ "$rc" = 3 ]; then
    echo "[配额] 当日额度用完,退出;明天重跑本脚本续跑。"
    exit 3
  elif [ "$rc" != 0 ]; then
    echo "[错误] 退出码 $rc"
    exit "$rc"
  fi
  rc=0
}

run $PY download/download_meta.py
run $PY download/download_indices.py
run $PY download/download_daily.py
run $PY download/download_nonprice.py
run $PY download/download_macro.py
run $PY download/download_options.py
if [ "$NO_5M" = 0 ]; then
  run $PY download/download_5minute.py
fi
run $PY download/validate.py
echo "全部完成。"
