# 故障恢复演练证据(design_log 18.2 第 5 项)

验收程序 `scripts/paper_acceptance.py` 只认本目录下的结构化 JSON 证据;没有合格证据时报告显示 **PENDING**,不凭空判定通过。

每次演练一个文件 `YYYY-MM-DD_<简述>.json`,必需字段:

```json
{
  "date": "2026-10-08",
  "book": "paper/v03",
  "injected": "删除 data/exchanges/CZCE/quotes/2026/20261008.parquet 后运行 catchup",
  "detected": {"failed_json": true, "exit_code": 1, "notification": true, "stage": "settle"},
  "recovered": {"action": "恢复文件后 .venv/bin/python -m cta.cli paper catchup --date 2026-10-08 --book paper/v03 --no-ingest --config configs/strategy_v03.yaml", "duration_s": 95},
  "outcome": "state.json 推进到 2026-10-08,equity.csv 无重复行,FAILED.json 自动清除,与未注入的重放逐字段一致",
  "operator": "s296he"
}
```

约束:演练只能在**账本副本**上做,或在真实账本上做后按手册恢复并留下 git 记录;证据里写明用的是哪一种。

副本怎么做(2026-10-16 第一次演练的做法):
1. 另开一个 worktree;`data/exchanges` **复制**过去(约 1.3 GB),不要按 CLAUDE.md 的常规做法软链接——软链接下删文件删的是主检出里每日任务共用的那一份;`data/ricecta`、`data/external` 照常软链接。
2. 账本副本用 `git archive <某个已结算日的提交> paper/v03 | tar -x` 取出,放到 `paper/drill_v03` 之类的名字下(不要叫 `paper/v03`)。
3. 删的是**副本数据仓**里的文件;上面示例的路径指副本。`quotes_all.parquet` 缓存按文件数判断是否过期,删文件后会自动重建,恢复后再重建一次。
4. 只跑 `cta.cli paper catchup`,不要在副本上跑 `scripts/paper_daily.sh`(它会提交并推送)。CLI 不发桌面通知,`notification` 一项如实写"未测"或引用真实失败日的 cron.log。
5. 恢复后把 `fills/<日>.csv`、`equity.csv`、`positions.csv`、`orders/<日>/orders.csv`、`log/<日>.json`、`state.json` 与真实账本逐字节比对;`snapshot.json` 只会差 git_sha 与数据仓路径。
