# 纸面交易验收报告(PRELIMINARY,截至 2026-10-15)

**PRELIMINARY —— 验收期 2026-09-23 → 2026-12-15 尚未结束,本报告截至 2026-10-15,只是阶段性结果。**

预注册规则:`docs/design_log.md` 十八;协议清单:`configs/paper_protocol.yaml`;champion = `paper_v03`,challenger = `paper`, `paper_v03p`, `paper_v01r`, `paper_v05`。**不选赢家,不采用、不淘汰任何版本。**

## 0. 摘要

| 账本 | 角色 | 有数据/预期交易日 | 成交率 | 权益对账 | 持仓对账 | 失败记录(已修复) | 未声明漂移 |
|---|---|---|---|---|---|---|---|
| paper_v03 | champion | 11/11 | 100.0% | 一致 | 一致 | 2(2) | 0 |
| paper | challenger | 11/11 | 100.0% | 一致 | 一致 | 2(2) | 0 |
| paper_v03p | challenger | 11/11 | 100.0% | 一致 | 一致 | 2(2) | 0 |
| paper_v01r | challenger | 11/11 | 100.0% | 一致 | 一致 | 2(2) | 0 |
| paper_v05 | challenger | 11/11 | 100.0% | 一致 | 一致 | 2(2) | 0 |

预期交易日 = 周一至周五且不在 `configs/holidays.csv`,2026-09-23 → 2026-10-15 共 11 天。五本账共同有效日期:2026-09-16 → 2026-10-15(16 天)。

## 1. 数据完整率

| 账本 | 预期 | 有数据 | 完整率 | 缺失日期 |
|---|---|---|---|---|
| paper_v03 | 11 | 11 | 100.0% | — |
| paper | 11 | 11 | 100.0% | — |
| paper_v03p | 11 | 11 | 100.0% | — |
| paper_v01r | 11 | 11 | 100.0% | — |
| paper_v05 | 11 | 11 | 100.0% | — |

预注册阈值:验收期内每个交易日五本账都有权益行(FAILED 日在后续运行中修复重放算完整;最终仍缺失 → 不通过)。

## 2. 成交率(按腿)

| 账本 | filled | blocked | filled/(filled+blocked) |
|---|---|---|---|
| paper_v03 | 37 | 0 | 100.0% |
| paper | 35 | 0 | 100.0% |
| paper_v03p | 42 | 0 | 100.0% |
| paper_v01r | 35 | 0 | 100.0% |
| paper_v05 | 11 | 0 | 100.0% |

阈值 ≥ 95%。blocked 逐条:

(无)

## 3. 权益对账(账本语义:Δ权益 = Δ已实现 + 当日盯市 − Δ手续费;滑点已在成交价内,不再扣)

逐日检查 55 条,不一致 0 条;容差 1e-4 元(浮点)。另用当日 fills 交叉核对手续费(旧格式 fills 无 realized_pnl 列,只核手续费)。

| 账本 | 周 | 天数 | 最大|差| | 通过 |
|---|---|---|---|---|
| paper | 2026-W39 | 2 | 0.000000 | 是 |
| paper | 2026-W40 | 3 | 0.000000 | 是 |
| paper | 2026-W41 | 2 | 0.000000 | 是 |
| paper | 2026-W42 | 4 | 0.000000 | 是 |
| paper_v01r | 2026-W39 | 2 | 0.000000 | 是 |
| paper_v01r | 2026-W40 | 3 | 0.000000 | 是 |
| paper_v01r | 2026-W41 | 2 | 0.000000 | 是 |
| paper_v01r | 2026-W42 | 4 | 0.000000 | 是 |
| paper_v03 | 2026-W39 | 2 | 0.000000 | 是 |
| paper_v03 | 2026-W40 | 3 | 0.000000 | 是 |
| paper_v03 | 2026-W41 | 2 | 0.000000 | 是 |
| paper_v03 | 2026-W42 | 4 | 0.000000 | 是 |
| paper_v03p | 2026-W39 | 2 | 0.000000 | 是 |
| paper_v03p | 2026-W40 | 3 | 0.000000 | 是 |
| paper_v03p | 2026-W41 | 2 | 0.000000 | 是 |
| paper_v03p | 2026-W42 | 4 | 0.000000 | 是 |
| paper_v05 | 2026-W39 | 2 | 0.000000 | 是 |
| paper_v05 | 2026-W40 | 3 | 0.000000 | 是 |
| paper_v05 | 2026-W41 | 2 | 0.000000 | 是 |
| paper_v05 | 2026-W42 | 4 | 0.000000 | 是 |

## 4. 持仓对账(18.2 第 4 项:前一日持仓 + 当日成交腿 = 当日持仓 = 前一日订单目标;有腿未成交的品种保持前一日持仓)

逐日检查 55 条(账本日志 `log/<日>.json` 的持仓、`fills/<日>.csv`、`orders/<前一日>/orders.csv`),不一致 0 条。

| 账本 | 周 | 天数 | 不一致 | 通过 |
|---|---|---|---|---|
| paper | 2026-W39 | 2 | 0 | 是 |
| paper | 2026-W40 | 3 | 0 | 是 |
| paper | 2026-W41 | 2 | 0 | 是 |
| paper | 2026-W42 | 4 | 0 | 是 |
| paper_v01r | 2026-W39 | 2 | 0 | 是 |
| paper_v01r | 2026-W40 | 3 | 0 | 是 |
| paper_v01r | 2026-W41 | 2 | 0 | 是 |
| paper_v01r | 2026-W42 | 4 | 0 | 是 |
| paper_v03 | 2026-W39 | 2 | 0 | 是 |
| paper_v03 | 2026-W40 | 3 | 0 | 是 |
| paper_v03 | 2026-W41 | 2 | 0 | 是 |
| paper_v03 | 2026-W42 | 4 | 0 | 是 |
| paper_v03p | 2026-W39 | 2 | 0 | 是 |
| paper_v03p | 2026-W40 | 3 | 0 | 是 |
| paper_v03p | 2026-W41 | 2 | 0 | 是 |
| paper_v03p | 2026-W42 | 4 | 0 | 是 |
| paper_v05 | 2026-W39 | 2 | 0 | 是 |
| paper_v05 | 2026-W40 | 3 | 0 | 是 |
| paper_v05 | 2026-W41 | 2 | 0 | 是 |
| paper_v05 | 2026-W42 | 4 | 0 | 是 |

最新一日 `state.json` 持仓 = 当日日志持仓 = `positions.csv`:

| 账本 | 日期 | 持仓品种数 | 对日志 | 对 positions.csv | 说明 |
|---|---|---|---|---|---|
| paper_v03 | 2026-10-15 | 17 | 一致 | 一致 |  |
| paper | 2026-10-15 | 17 | 一致 | 一致 |  |
| paper_v03p | 2026-10-15 | 15 | 一致 | 一致 |  |
| paper_v01r | 2026-10-15 | 17 | 一致 | 一致 |  |
| paper_v05 | 2026-10-15 | 9 | 一致 | 一致 |  |

## 5. 失败记录(工作区 FAILED.json、日志,以及 git 历史里已被成功重放清除的 FAILED.json)

| 账本 | 日期 | 阶段 | 错误 | 来源 | 状态 |
|---|---|---|---|---|---|
| paper_v03 | 2026-09-23 | settle | LedgerIntegrityError: held contracts without a finite settlement price: ['C:C2611', 'I:I2701', 'J:J2701', 'JD:JD2611', 'M:M2701', 'P:P2701', 'V:V2701', 'Y:Y2701'] | git 6ca29ab | 已修复(重放补齐) |
| paper_v03 | 2026-10-08 | settle | LedgerIntegrityError: held contracts without a finite settlement price: ['C:C2611', 'I:I2701', 'J:J2701', 'JD:JD2611', 'M:M2701', 'V:V2701', 'Y:Y2701', 'P:P2701'] | git 091c7aa | 已修复(重放补齐) |
| paper | 2026-09-23 | settle | LedgerIntegrityError: held contracts without a finite settlement price: ['C:C2611', 'JD:JD2611', 'M:M2701', 'P:P2701', 'V:V2701', 'Y:Y2701', 'I:I2701'] | git 6ca29ab | 已修复(重放补齐) |
| paper | 2026-10-08 | settle | LedgerIntegrityError: held contracts without a finite settlement price: ['C:C2611', 'JD:JD2611', 'M:M2701', 'P:P2701', 'V:V2701', 'Y:Y2701', 'I:I2701'] | git 091c7aa | 已修复(重放补齐) |
| paper_v03p | 2026-09-23 | settle | LedgerIntegrityError: held contracts without a finite settlement price: ['C:C2611', 'I:I2701', 'J:J2701', 'JD:JD2611', 'P:P2701', 'V:V2701', 'Y:Y2701'] | git 6ca29ab | 已修复(重放补齐) |
| paper_v03p | 2026-10-08 | settle | LedgerIntegrityError: held contracts without a finite settlement price: ['C:C2611', 'I:I2701', 'J:J2701', 'P:P2701', 'V:V2701', 'JD:JD2611'] | git 091c7aa | 已修复(重放补齐) |
| paper_v01r | 2026-09-23 | settle | LedgerIntegrityError: held contracts without a finite settlement price: ['C:C2611', 'JD:JD2611', 'M:M2701', 'P:P2701', 'V:V2701', 'Y:Y2701', 'I:I2701'] | git 6ca29ab | 已修复(重放补齐) |
| paper_v01r | 2026-10-08 | settle | LedgerIntegrityError: held contracts without a finite settlement price: ['C:C2611', 'JD:JD2611', 'M:M2701', 'P:P2701', 'V:V2701', 'Y:Y2701', 'I:I2701'] | git 091c7aa | 已修复(重放补齐) |
| paper_v05 | 2026-09-23 | settle | LedgerIntegrityError: held contracts without a finite settlement price: ['V:V2701'] | git 6ca29ab | 已修复(重放补齐) |
| paper_v05 | 2026-10-08 | settle | LedgerIntegrityError: held contracts without a finite settlement price: ['V:V2701'] | git 091c7aa | 已修复(重放补齐) |

已修复 = 该日现已有权益行且无 FAILED.json(18.2 第 1 项:FAILED 日在后续运行中修复重放算完整);未修复的失败日同时出现在第 1 节的缺失日期里。

## 6. 配置 / 参数表 / 代码 / 数据漂移(基于订单快照 config_digest、instruments_digest、git_sha、data_manifest)

| 账本 | 日期 | 字段 | 旧 | 新 | 分类 | 已声明 | 说明 |
|---|---|---|---|---|---|---|---|
| paper_v03 | 2026-09-23 | config_digest | 2c6027c9b2f3 | 5b010148a71e | 策略配置变化 | 是 | 统一执行口径(design_log 17.7):trade_buffer 拆成 exposure_buffer/lot_band、新增 data.settle=official;代码 dd215f5 → f898e7b 及之后 |
| paper_v03 | 2026-09-23 | git_sha | dd215f5 | 6ca29ab | 代码变化 | 是 | 统一执行口径(design_log 17.7):trade_buffer 拆成 exposure_buffer/lot_band、新增 data.settle=official;代码 dd215f5 → f898e7b 及之后;账本路径改动 24 个文件:configs/strategy.yaml, configs/strategy_v01r.yaml, configs/strategy_v03.yaml, configs/strategy_v03p.yaml… |
| paper_v03 | 2026-09-23 | secondary_sha | cb29c00f97829ac3 | e714837f9de7cee6 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v03 | 2026-09-28 | git_sha | 6ca29ab | f632778 | 代码变化 | 是 | 只新增 src/cta/analysis 下三个研究模块(季度自适应、基本面信号、walk-forward),纸面路径不导入(design_log 十九至二十一;五本账不受影响);账本路径改动 3 个文件:src/cta/analysis/adaptive_quarterly.py, src/cta/analysis/fundamental_signals.py, src/cta/analysis/walkforward.py |
| paper_v03 | 2026-09-28 | secondary_sha | e714837f9de7cee6 | 72918471598cd507 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v03 | 2026-09-29 | git_sha | f632778 | a51b685 | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper_v03 | 2026-09-29 | secondary_sha | 72918471598cd507 | 76344fc80e87b978 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v03 | 2026-09-30 | git_sha | a51b685 | 214cef1 | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper_v03 | 2026-09-30 | secondary_sha | 76344fc80e87b978 | bf5438f34ef36f40 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v03 | 2026-10-08 | git_sha | 214cef1 | 091c7aa | 代码变化 | 是 | 仓库整理(五本账移入 paper/,design_log 二十六:迁移前五本账 step 均 already settled、state.json 逐字节相同)、MSF 可选外部因子挂钩(二十五:现有配置输出逐位不变)、另类数据/期权研究管道(当时在 src/cta 下,纸面路径不导入)、paper_daily.sh 路径更新;账本路径改动 27 个文件:scripts/paper_daily.sh, src/cta/analysis/adaptive_quarterly.py, src/cta/analysis/altdata_signals.py, src/cta/analysis/candidate_eval.py… |
| paper_v03 | 2026-10-08 | secondary_sha | bf5438f34ef36f40 | 73973b75be30d842 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v03 | 2026-10-09 | git_sha | 091c7aa | 1ca982a | 代码变化 | 是 | Python 3.12 .venv 与依赖固定(design_log 27.1:五本账目标暴露逐位相同、09-30 订单相同)、研究/生产代码分离(27.5:纯移动)、交易所数据源可选 dominant_rule(默认 max_oi 不变,27.3);账本路径改动 31 个文件:requirements-dev.txt, requirements.txt, scripts/paper_daily.sh, src/cta/analysis/adaptive_quarterly.py… |
| paper_v03 | 2026-10-09 | secondary_sha | 73973b75be30d842 | b528eedf5012af36 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v03 | 2026-10-12 | git_sha | 1ca982a | c8d08df | 代码变化 | 是 | 按流程阶段分文件夹(design_log 二十九:六个配置 golden 输出逐字节相同、五本账 10-08/10-09 回放逐字节相同)、交易日历默认假期表修复(三十:回放与 golden 逐字节相同,追加 2027 假期前生产行为不变);账本路径改动 33 个文件:src/cta/analysis/attribution.py, src/cta/analysis/loo.py, src/cta/analysis/metrics.py, src/cta/analysis/report.py… |
| paper_v03 | 2026-10-12 | secondary_sha | b528eedf5012af36 | 073dc7082fb78ec9 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v03 | 2026-10-13 | git_sha | c8d08df | 8b585f5 | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper_v03 | 2026-10-13 | secondary_sha | 073dc7082fb78ec9 | 7b5fbbf486c26581 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v03 | 2026-10-14 | git_sha | 8b585f5 | cf42df5 | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper_v03 | 2026-10-14 | secondary_sha | 7b5fbbf486c26581 | 751b4237e59ccb4b | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v03 | 2026-10-15 | git_sha | cf42df5 | c2953ad | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper_v03 | 2026-10-15 | secondary_sha | 751b4237e59ccb4b | ce6ef5554c006f4e | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper | 2026-09-23 | config_digest | 60268efc5b9c | 2061059f500b | 策略配置变化 | 是 | 统一执行口径(design_log 17.7):trade_buffer 拆成 exposure_buffer/lot_band、新增 data.settle=official;代码 dd215f5 → f898e7b 及之后 |
| paper | 2026-09-23 | git_sha | dd215f5 | 6ca29ab | 代码变化 | 是 | 统一执行口径(design_log 17.7):trade_buffer 拆成 exposure_buffer/lot_band、新增 data.settle=official;代码 dd215f5 → f898e7b 及之后;账本路径改动 24 个文件:configs/strategy.yaml, configs/strategy_v01r.yaml, configs/strategy_v03.yaml, configs/strategy_v03p.yaml… |
| paper | 2026-09-23 | secondary_sha | cb29c00f97829ac3 | 1f48b4a30492a9c3 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper | 2026-09-24 | secondary_sha | 1f48b4a30492a9c3 | e714837f9de7cee6 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper | 2026-09-28 | git_sha | 6ca29ab | f632778 | 代码变化 | 是 | 只新增 src/cta/analysis 下三个研究模块(季度自适应、基本面信号、walk-forward),纸面路径不导入(design_log 十九至二十一;五本账不受影响);账本路径改动 3 个文件:src/cta/analysis/adaptive_quarterly.py, src/cta/analysis/fundamental_signals.py, src/cta/analysis/walkforward.py |
| paper | 2026-09-28 | secondary_sha | e714837f9de7cee6 | 72918471598cd507 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper | 2026-09-29 | git_sha | f632778 | a51b685 | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper | 2026-09-29 | secondary_sha | 72918471598cd507 | 76344fc80e87b978 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper | 2026-09-30 | git_sha | a51b685 | 214cef1 | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper | 2026-09-30 | secondary_sha | 76344fc80e87b978 | bf5438f34ef36f40 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper | 2026-10-08 | git_sha | 214cef1 | 091c7aa | 代码变化 | 是 | 仓库整理(五本账移入 paper/,design_log 二十六:迁移前五本账 step 均 already settled、state.json 逐字节相同)、MSF 可选外部因子挂钩(二十五:现有配置输出逐位不变)、另类数据/期权研究管道(当时在 src/cta 下,纸面路径不导入)、paper_daily.sh 路径更新;账本路径改动 27 个文件:scripts/paper_daily.sh, src/cta/analysis/adaptive_quarterly.py, src/cta/analysis/altdata_signals.py, src/cta/analysis/candidate_eval.py… |
| paper | 2026-10-08 | secondary_sha | bf5438f34ef36f40 | 73973b75be30d842 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper | 2026-10-09 | git_sha | 091c7aa | 1ca982a | 代码变化 | 是 | Python 3.12 .venv 与依赖固定(design_log 27.1:五本账目标暴露逐位相同、09-30 订单相同)、研究/生产代码分离(27.5:纯移动)、交易所数据源可选 dominant_rule(默认 max_oi 不变,27.3);账本路径改动 31 个文件:requirements-dev.txt, requirements.txt, scripts/paper_daily.sh, src/cta/analysis/adaptive_quarterly.py… |
| paper | 2026-10-09 | secondary_sha | 73973b75be30d842 | b528eedf5012af36 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper | 2026-10-12 | git_sha | 1ca982a | c8d08df | 代码变化 | 是 | 按流程阶段分文件夹(design_log 二十九:六个配置 golden 输出逐字节相同、五本账 10-08/10-09 回放逐字节相同)、交易日历默认假期表修复(三十:回放与 golden 逐字节相同,追加 2027 假期前生产行为不变);账本路径改动 33 个文件:src/cta/analysis/attribution.py, src/cta/analysis/loo.py, src/cta/analysis/metrics.py, src/cta/analysis/report.py… |
| paper | 2026-10-12 | secondary_sha | b528eedf5012af36 | 073dc7082fb78ec9 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper | 2026-10-13 | git_sha | c8d08df | 8b585f5 | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper | 2026-10-13 | secondary_sha | 073dc7082fb78ec9 | 7b5fbbf486c26581 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper | 2026-10-14 | git_sha | 8b585f5 | cf42df5 | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper | 2026-10-14 | secondary_sha | 7b5fbbf486c26581 | 751b4237e59ccb4b | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper | 2026-10-15 | git_sha | cf42df5 | c2953ad | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper | 2026-10-15 | secondary_sha | 751b4237e59ccb4b | ce6ef5554c006f4e | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v03p | 2026-09-23 | config_digest | d7e5e879050c | 854e88a275e7 | 策略配置变化 | 是 | 统一执行口径(design_log 17.7):trade_buffer 拆成 exposure_buffer/lot_band、新增 data.settle=official;代码 dd215f5 → f898e7b 及之后 |
| paper_v03p | 2026-09-23 | git_sha | dd215f5 | 6ca29ab | 代码变化 | 是 | 统一执行口径(design_log 17.7):trade_buffer 拆成 exposure_buffer/lot_band、新增 data.settle=official;代码 dd215f5 → f898e7b 及之后;账本路径改动 24 个文件:configs/strategy.yaml, configs/strategy_v01r.yaml, configs/strategy_v03.yaml, configs/strategy_v03p.yaml… |
| paper_v03p | 2026-09-23 | secondary_sha | cb29c00f97829ac3 | e714837f9de7cee6 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v03p | 2026-09-28 | git_sha | 6ca29ab | f632778 | 代码变化 | 是 | 只新增 src/cta/analysis 下三个研究模块(季度自适应、基本面信号、walk-forward),纸面路径不导入(design_log 十九至二十一;五本账不受影响);账本路径改动 3 个文件:src/cta/analysis/adaptive_quarterly.py, src/cta/analysis/fundamental_signals.py, src/cta/analysis/walkforward.py |
| paper_v03p | 2026-09-28 | secondary_sha | e714837f9de7cee6 | 72918471598cd507 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v03p | 2026-09-29 | git_sha | f632778 | a51b685 | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper_v03p | 2026-09-29 | secondary_sha | 72918471598cd507 | 76344fc80e87b978 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v03p | 2026-09-30 | git_sha | a51b685 | 214cef1 | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper_v03p | 2026-09-30 | secondary_sha | 76344fc80e87b978 | bf5438f34ef36f40 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v03p | 2026-10-08 | git_sha | 214cef1 | 091c7aa | 代码变化 | 是 | 仓库整理(五本账移入 paper/,design_log 二十六:迁移前五本账 step 均 already settled、state.json 逐字节相同)、MSF 可选外部因子挂钩(二十五:现有配置输出逐位不变)、另类数据/期权研究管道(当时在 src/cta 下,纸面路径不导入)、paper_daily.sh 路径更新;账本路径改动 27 个文件:scripts/paper_daily.sh, src/cta/analysis/adaptive_quarterly.py, src/cta/analysis/altdata_signals.py, src/cta/analysis/candidate_eval.py… |
| paper_v03p | 2026-10-08 | secondary_sha | bf5438f34ef36f40 | 73973b75be30d842 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v03p | 2026-10-09 | git_sha | 091c7aa | 1ca982a | 代码变化 | 是 | Python 3.12 .venv 与依赖固定(design_log 27.1:五本账目标暴露逐位相同、09-30 订单相同)、研究/生产代码分离(27.5:纯移动)、交易所数据源可选 dominant_rule(默认 max_oi 不变,27.3);账本路径改动 31 个文件:requirements-dev.txt, requirements.txt, scripts/paper_daily.sh, src/cta/analysis/adaptive_quarterly.py… |
| paper_v03p | 2026-10-09 | secondary_sha | 73973b75be30d842 | b528eedf5012af36 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v03p | 2026-10-12 | git_sha | 1ca982a | c8d08df | 代码变化 | 是 | 按流程阶段分文件夹(design_log 二十九:六个配置 golden 输出逐字节相同、五本账 10-08/10-09 回放逐字节相同)、交易日历默认假期表修复(三十:回放与 golden 逐字节相同,追加 2027 假期前生产行为不变);账本路径改动 33 个文件:src/cta/analysis/attribution.py, src/cta/analysis/loo.py, src/cta/analysis/metrics.py, src/cta/analysis/report.py… |
| paper_v03p | 2026-10-12 | secondary_sha | b528eedf5012af36 | 073dc7082fb78ec9 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v03p | 2026-10-13 | git_sha | c8d08df | 8b585f5 | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper_v03p | 2026-10-13 | secondary_sha | 073dc7082fb78ec9 | 7b5fbbf486c26581 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v03p | 2026-10-14 | git_sha | 8b585f5 | cf42df5 | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper_v03p | 2026-10-14 | secondary_sha | 7b5fbbf486c26581 | 751b4237e59ccb4b | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v03p | 2026-10-15 | git_sha | cf42df5 | c2953ad | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper_v03p | 2026-10-15 | secondary_sha | 751b4237e59ccb4b | ce6ef5554c006f4e | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v01r | 2026-09-23 | config_digest | aa4eed650bb2 | de2edea33b5d | 策略配置变化 | 是 | 统一执行口径(design_log 17.7):trade_buffer 拆成 exposure_buffer/lot_band、新增 data.settle=official;代码 dd215f5 → f898e7b 及之后 |
| paper_v01r | 2026-09-23 | git_sha | dd215f5 | 6ca29ab | 代码变化 | 是 | 统一执行口径(design_log 17.7):trade_buffer 拆成 exposure_buffer/lot_band、新增 data.settle=official;代码 dd215f5 → f898e7b 及之后;账本路径改动 24 个文件:configs/strategy.yaml, configs/strategy_v01r.yaml, configs/strategy_v03.yaml, configs/strategy_v03p.yaml… |
| paper_v01r | 2026-09-23 | secondary_sha | cb29c00f97829ac3 | e714837f9de7cee6 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v01r | 2026-09-28 | git_sha | 6ca29ab | f632778 | 代码变化 | 是 | 只新增 src/cta/analysis 下三个研究模块(季度自适应、基本面信号、walk-forward),纸面路径不导入(design_log 十九至二十一;五本账不受影响);账本路径改动 3 个文件:src/cta/analysis/adaptive_quarterly.py, src/cta/analysis/fundamental_signals.py, src/cta/analysis/walkforward.py |
| paper_v01r | 2026-09-28 | secondary_sha | e714837f9de7cee6 | 72918471598cd507 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v01r | 2026-09-29 | git_sha | f632778 | a51b685 | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper_v01r | 2026-09-29 | secondary_sha | 72918471598cd507 | 76344fc80e87b978 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v01r | 2026-09-30 | git_sha | a51b685 | 214cef1 | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper_v01r | 2026-09-30 | secondary_sha | 76344fc80e87b978 | bf5438f34ef36f40 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v01r | 2026-10-08 | git_sha | 214cef1 | 091c7aa | 代码变化 | 是 | 仓库整理(五本账移入 paper/,design_log 二十六:迁移前五本账 step 均 already settled、state.json 逐字节相同)、MSF 可选外部因子挂钩(二十五:现有配置输出逐位不变)、另类数据/期权研究管道(当时在 src/cta 下,纸面路径不导入)、paper_daily.sh 路径更新;账本路径改动 27 个文件:scripts/paper_daily.sh, src/cta/analysis/adaptive_quarterly.py, src/cta/analysis/altdata_signals.py, src/cta/analysis/candidate_eval.py… |
| paper_v01r | 2026-10-08 | secondary_sha | bf5438f34ef36f40 | 73973b75be30d842 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v01r | 2026-10-09 | git_sha | 091c7aa | 1ca982a | 代码变化 | 是 | Python 3.12 .venv 与依赖固定(design_log 27.1:五本账目标暴露逐位相同、09-30 订单相同)、研究/生产代码分离(27.5:纯移动)、交易所数据源可选 dominant_rule(默认 max_oi 不变,27.3);账本路径改动 31 个文件:requirements-dev.txt, requirements.txt, scripts/paper_daily.sh, src/cta/analysis/adaptive_quarterly.py… |
| paper_v01r | 2026-10-09 | secondary_sha | 73973b75be30d842 | b528eedf5012af36 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v01r | 2026-10-12 | git_sha | 1ca982a | c8d08df | 代码变化 | 是 | 按流程阶段分文件夹(design_log 二十九:六个配置 golden 输出逐字节相同、五本账 10-08/10-09 回放逐字节相同)、交易日历默认假期表修复(三十:回放与 golden 逐字节相同,追加 2027 假期前生产行为不变);账本路径改动 33 个文件:src/cta/analysis/attribution.py, src/cta/analysis/loo.py, src/cta/analysis/metrics.py, src/cta/analysis/report.py… |
| paper_v01r | 2026-10-12 | secondary_sha | b528eedf5012af36 | 073dc7082fb78ec9 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v01r | 2026-10-13 | git_sha | c8d08df | 8b585f5 | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper_v01r | 2026-10-13 | secondary_sha | 073dc7082fb78ec9 | 7b5fbbf486c26581 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v01r | 2026-10-14 | git_sha | 8b585f5 | cf42df5 | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper_v01r | 2026-10-14 | secondary_sha | 7b5fbbf486c26581 | 751b4237e59ccb4b | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v01r | 2026-10-15 | git_sha | cf42df5 | c2953ad | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper_v01r | 2026-10-15 | secondary_sha | 751b4237e59ccb4b | ce6ef5554c006f4e | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v05 | 2026-09-23 | config_digest | 81513c8204da | 764ae2e20153 | 策略配置变化 | 是 | 统一执行口径(design_log 17.7):trade_buffer 拆成 exposure_buffer/lot_band、新增 data.settle=official;代码 dd215f5 → f898e7b 及之后 |
| paper_v05 | 2026-09-23 | git_sha | dd215f5 | 6ca29ab | 代码变化 | 是 | 统一执行口径(design_log 17.7):trade_buffer 拆成 exposure_buffer/lot_band、新增 data.settle=official;代码 dd215f5 → f898e7b 及之后;账本路径改动 24 个文件:configs/strategy.yaml, configs/strategy_v01r.yaml, configs/strategy_v03.yaml, configs/strategy_v03p.yaml… |
| paper_v05 | 2026-09-23 | secondary_sha | cb29c00f97829ac3 | e714837f9de7cee6 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v05 | 2026-09-28 | git_sha | 6ca29ab | f632778 | 代码变化 | 是 | 只新增 src/cta/analysis 下三个研究模块(季度自适应、基本面信号、walk-forward),纸面路径不导入(design_log 十九至二十一;五本账不受影响);账本路径改动 3 个文件:src/cta/analysis/adaptive_quarterly.py, src/cta/analysis/fundamental_signals.py, src/cta/analysis/walkforward.py |
| paper_v05 | 2026-09-28 | secondary_sha | e714837f9de7cee6 | 72918471598cd507 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v05 | 2026-09-29 | git_sha | f632778 | a51b685 | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper_v05 | 2026-09-29 | secondary_sha | 72918471598cd507 | 76344fc80e87b978 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v05 | 2026-09-30 | git_sha | a51b685 | 214cef1 | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper_v05 | 2026-09-30 | secondary_sha | 76344fc80e87b978 | bf5438f34ef36f40 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v05 | 2026-10-08 | git_sha | 214cef1 | 091c7aa | 代码变化 | 是 | 仓库整理(五本账移入 paper/,design_log 二十六:迁移前五本账 step 均 already settled、state.json 逐字节相同)、MSF 可选外部因子挂钩(二十五:现有配置输出逐位不变)、另类数据/期权研究管道(当时在 src/cta 下,纸面路径不导入)、paper_daily.sh 路径更新;账本路径改动 27 个文件:scripts/paper_daily.sh, src/cta/analysis/adaptive_quarterly.py, src/cta/analysis/altdata_signals.py, src/cta/analysis/candidate_eval.py… |
| paper_v05 | 2026-10-08 | secondary_sha | bf5438f34ef36f40 | 73973b75be30d842 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v05 | 2026-10-09 | git_sha | 091c7aa | 1ca982a | 代码变化 | 是 | Python 3.12 .venv 与依赖固定(design_log 27.1:五本账目标暴露逐位相同、09-30 订单相同)、研究/生产代码分离(27.5:纯移动)、交易所数据源可选 dominant_rule(默认 max_oi 不变,27.3);账本路径改动 31 个文件:requirements-dev.txt, requirements.txt, scripts/paper_daily.sh, src/cta/analysis/adaptive_quarterly.py… |
| paper_v05 | 2026-10-09 | secondary_sha | 73973b75be30d842 | b528eedf5012af36 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v05 | 2026-10-12 | git_sha | 1ca982a | c8d08df | 代码变化 | 是 | 按流程阶段分文件夹(design_log 二十九:六个配置 golden 输出逐字节相同、五本账 10-08/10-09 回放逐字节相同)、交易日历默认假期表修复(三十:回放与 golden 逐字节相同,追加 2027 假期前生产行为不变);账本路径改动 33 个文件:src/cta/analysis/attribution.py, src/cta/analysis/loo.py, src/cta/analysis/metrics.py, src/cta/analysis/report.py… |
| paper_v05 | 2026-10-12 | secondary_sha | b528eedf5012af36 | 073dc7082fb78ec9 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v05 | 2026-10-13 | git_sha | c8d08df | 8b585f5 | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper_v05 | 2026-10-13 | secondary_sha | 073dc7082fb78ec9 | 7b5fbbf486c26581 | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v05 | 2026-10-14 | git_sha | 8b585f5 | cf42df5 | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper_v05 | 2026-10-14 | secondary_sha | 7b5fbbf486c26581 | 751b4237e59ccb4b | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |
| paper_v05 | 2026-10-15 | git_sha | cf42df5 | c2953ad | 代码变化 | 是 | 仅非账本路径的提交(文档、研究代码或纸面数据):src/cta、每日脚本、依赖、五本账配置、参数表、假期表无改动 |
| paper_v05 | 2026-10-15 | secondary_sha | 751b4237e59ccb4b | ce6ef5554c006f4e | 数据增量(交易所段,预期每日变化) | 是 | 交易所数据每日增量 |

默认只检测和报告,不阻止每日作业。协议清单声明的切换视为合法;未声明的策略配置/参数表/代码/数据版本变化需要解释。git_sha 每个纸面提交都会变:两个版本之间若 `src/cta`、每日脚本、依赖、五本账配置、参数表、假期表都没改,记为'仅非账本路径的提交',算已声明;改了则须在清单里声明(同日或 from → to),否则列出改动文件。

## 7. 故障恢复演练证据

状态:**DONE**(证据目录 `docs/drills/*.json`,必需字段 date, book, injected, detected, recovered, outcome;没有合格证据即 PENDING,不凭空判定通过)。

- `2026-10-16_czce_quotes_copy.json`:合格 —— 2026-10-15 paper/v03 注入 删除副本数据仓的 data/exchanges/CZCE/quotes/2026/20261015.parquet 后运行 .venv/bin/python -m cta.cli paper catchup --date 2026-10-15 --no-ingest --book paper/drill_v03 --config configs/strategy_v03.yaml / 检出 {'failed_json': True, 'exit_code': 1, 'stage': 'settle', 'error': "LedgerIntegrityError: held contracts without a finite settlement price: ['MA:MA2701', 'SA:SA2701', 'SR:SR2701', 'TA:TA2701', 'CF:CF2701']", 'duration_s': 3, 'state_unchanged': 'state.json 的 last_settled 仍为 2026-10-14;.txn/2026-10-15 留作取证', 'notification': '未测:通知由 scripts/paper_daily.sh 发出(osascript),CLI 不发;副本上不运行每日脚本(它会提交并推送)。真实失败 2026-09-23、10-08 的通知见 paper/log/cron.log'} / 恢复 {'action': '把同一文件从主检出复制回副本数据仓,重跑同一条 catchup 命令', 'exit_code': 0, 'duration_s': 18} / 结果 state.json 推进到 2026-10-15,FAILED.json 自动清除,equity.csv 无重复日期;fills/2026-10-15.csv、equity.csv、positions.csv、orders/2026-10-15/orders.csv、log/2026-10-15.json、state.json 与真实 paper/v03 逐字节相同;orders/2026-10-15/snapshot.json 只差 git_sha(10a9b1c vs c2953ad)与数据仓路径及由路径算出的清单哈希

## 8. 滑点校准(18.2 第 3 项;只报告,不判定)

每条成交腿:交易所开盘价 − 当日成交均价(成交额 / 成交量 / 乘数;上期所、能源中心成交额单位万元),以跳数计;成交价 − 开盘价是账本假设的 ±1 跳;side × (成交价 − 均价) 正 = 比当日均价差。交易所不公布首 bar 均价,全日均价是预注册写定的口径。按品种的明细在 `slippage_by_symbol.csv`,逐腿在 `slippage_legs.csv`。

| 账本 | 腿数 | 缺行情 | 开盘−均价 跳数:均值 / 中位 / p10 / p90 | 开盘−均价 平均|bp| | 成交−开盘 跳数均值 | side×(成交−均价) 跳数均值 |
|---|---|---|---|---|---|---|
| paper | 35 | 0 | 5.82 / 3.59 / -21.68 / 41.09 | 44.2 | -0.20 | +0.87 |
| paper_v01r | 35 | 0 | 5.82 / 3.59 / -21.68 / 41.09 | 44.2 | -0.20 | +0.87 |
| paper_v03 | 37 | 0 | 26.15 / 9.81 / -21.52 / 72.95 | 49.0 | -0.19 | +10.02 |
| paper_v03p | 42 | 0 | 19.37 / 8.26 / -21.92 / 63.43 | 52.6 | -0.24 | +12.43 |
| paper_v05 | 11 | 0 | 91.86 / 9.81 / -25.74 / 91.28 | 64.7 | +0.09 | +78.75 |

champion `paper_v03` 按品种:

| 品种 | 腿数 | 缺行情 | 开盘−均价 跳数均值 / 中位 | p10 / p90 | 平均|bp| | side×(成交−均价) 跳数均值 |
|---|---|---|---|---|---|---|
| AL | 3 | 0 | 12.01 / 9.81 | 3.99 / 20.91 | 25.7 | +11.32 |
| C | 2 | 0 | 8.45 / 8.45 | 7.91 / 8.98 | 38.5 | +0.33 |
| CF | 4 | 0 | 5.42 / 1.79 | -9.06 / 22.81 | 45.1 | +0.44 |
| CU | 2 | 0 | 27.95 / 27.95 | 8.46 / 47.45 | 25.5 | +25.37 |
| I | 4 | 0 | -0.76 / -2.94 | -6.76 / 6.99 | 42.2 | -1.09 |
| JD | 6 | 0 | 11.96 / 13.51 | -21.60 / 43.97 | 71.3 | -10.53 |
| NI | 2 | 0 | 67.43 / 67.43 | 48.57 / 86.28 | 57.1 | -66.43 |
| P | 3 | 0 | 33.32 / 55.96 | -20.99 / 78.57 | 61.9 | +4.99 |
| RB | 2 | 0 | 7.89 / 7.89 | 4.09 / 11.69 | 25.6 | -6.89 |
| SA | 2 | 0 | 2.06 / 2.06 | -1.38 / 5.49 | 42.5 | -1.06 |
| SN | 3 | 0 | 190.36 / 119.82 | 75.37 / 333.57 | 46.6 | +148.52 |
| SR | 1 | 0 | -37.32 / -37.32 | -37.32 / -37.32 | 67.5 | -36.32 |
| V | 1 | 0 | 26.24 / 26.24 | 26.24 / 26.24 | 54.9 | +27.24 |
| Y | 2 | 0 | -23.17 / -23.17 | -71.17 / 24.82 | 67.0 | +24.17 |

## 9. champion / challenger 配对差(预注册 18.3;只报告,不选择)

> **样本量不足**:paper, paper_v03p, paper_v01r, paper_v05 的共同交易日少于 60 天(当前 11 天)。下面的数字只是记录,不能用来比较优劣;标准误按 17.5 的估计要 12 个月才降到 ±0.65。

| challenger | 共同日 | 配对差年化均值 | NW SE(年化) | t | bootstrap 95% 区间(年化) | 夏普(日频,champion / challenger) | 最大回撤(champion / challenger) | 回撤差 |
|---|---|---|---|---|---|---|---|---|
| paper | 11 | +51.12% | +14.94% | 3.42 | [+46.53%, +55.75%] | -3.58 / 2.03 | -1.66% / -0.95% | +0.70% |
| paper_v03p | 11 | +5.72% | +15.50% | 0.37 | [+5.51%, +7.46%] | -3.58 / -2.11 | -1.66% / -2.28% | -0.63% |
| paper_v01r | 11 | +51.12% | +14.94% | 3.42 | [+46.53%, +55.75%] | -3.58 / 2.03 | -1.66% / -0.95% | +0.70% |
| paper_v05 | 11 | +65.64% | +14.46% | 4.54 | [+58.05%, +68.08%] | -3.58 / 3.75 | -1.66% / -0.56% | +1.09% |

方法:d_t = challenger 日收益 − champion 日收益,各自以自身前一交易日权益为分母,只用双方共同有效日期;Newey–West lag=5;移动块 bootstrap 块长 10 个交易日、重采样 2000 次、随机种子 20260923(可复现);夏普为日频年化(243 个交易日),样本短时无意义。

预注册停账条件(唯一允许的动作):配对差 t < −3 且 challenger 回撤差 < −10pp,连续两个月末成立 → 可停账止损。**触及停账条件 ≠ champion 已被统计证明更优;未触及也不说明 challenger 更好。**

| challenger | 可评估 | 已评估月末数 | 是否触及 | 逐月 |
|---|---|---|---|---|
| paper | 是 | 2 | 未触及 | 否,否 |
| paper_v03p | 是 | 2 | 未触及 | 否,否 |
| paper_v01r | 是 | 2 | 未触及 | 否,否 |
| paper_v05 | 是 | 2 | 未触及 | 否,否 |

## 10. 方法与参数

- 输出目录:`results/paper_acceptance`;协议清单:`configs/paper_protocol.yaml`;随机种子 20260923;bootstrap 2000 次、块长 10;NW lag 5;权益对账容差 1e-4 元,持仓对账手数容差 1e-9。
- 本报告只读取 paper*/ 目录、git 历史与交易所行情文件,不修改任何账本文件;不新增账本;不据结果采用或淘汰版本。
- 与回测的比较(18.4)留到验收期结束再做;本阶段共同日期 16 天。
