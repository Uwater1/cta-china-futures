# 数据说明与已踩的坑

来源:米筐(Ricequant)导出,存于 `data/ricecta/data`(不随仓库分发)。23 个品种,2016-01-04 至 2026-06-05。

基准:`data/benchmarks/nhci_daily.csv` 为南华商品指数(NHCI,收益率指数)日收盘,2004-06-01 至 2026-09-11,取自南华期货官网行情网关(webhq.nanhua.net,WebSocket/protobuf,无 HTTP 接口;旧 akshare 接口已失效),2024-12-24 与 2025-12-19 两个点位已对照南华官方日报核验;随仓库分发(公开数据,125 KB)。

| 表 | 用途 | 注意 |
|---|---|---|
| `contracts_daily/<SYM>.parquet` | 合约级 OHLCV + 持仓量,(contract, date) 双索引 | 无结算价;结算以收盘价近似 |
| `contracts_daily/metadata.parquet` | 合约到期日、上市/退市日、乘数、保证金率 | **margin_rate 是临近交割抬高后的值**(CU 0.20 vs 常规 0.10),不能当日常保证金;`symbol` 列是中文简称,与品种代码列冲突 |
| `dominant_contracts/dominant.parquet` | 数据商每日主力合约 | 直接切换会产生回滚;本项目加 3 日确认且只向更晚到期切换 |
| `dominant_daily/<SYM>.parquet` | 主力连续日线(含结算价、涨跌停) | **是复权后的连续价**(与原始合约收盘比值 0.93–1.02),不能与原始合约价混用;本项目不使用 |
| `spot_basis/*.parquet` | 现货与基差 | 未用于 v0.1 |
| `shibor/shibor.parquet` | 利率 | 闲置资金收益的可选项(默认 0) |

品种覆盖:SA 自 2019-12、SC 自 2018-03,其余自 2016-01。TF(国债)为金融期货,不在商品 CTA 品种池。

展期收益的"次主力"到期间隔:金属(CU/AL/NI/SN)约 31 天、贵金属约 62 天、多数农产品与化工约 120 天(1/5/9 月合约)。
间隔越长,年化 carry 越受季节性影响;鸡蛋(JD)尤其明显(见设计日志二c)。

上线替换数据源时必须核对:合约乘数与跳价、涨跌幅与保证金的当日值、主力切换规则、夜盘日切与交易日历。

## 自建导出(`download/`,2026-10-15 起)

`download/` 下的脚本用 rqdatac 自建同口径导出(试用账号 1 GiB/天;幂等、断点续跑,配额不足时退出码 3,第二天重跑续)。完整清单和运行方式见 `download/README.md`。

- 兼容既有接口:`contracts_daily/<SYM>.parquet`(多一列 `total_turnover`)、`contracts_daily/metadata.parquet`、`dominant_contracts/dominant.parquet`、`dominant_daily/<SYM>.parquet`(前复权)、`shibor/shibor.parquet`、`futures_5minute/<SYM>/<CONTRACT>.parquet`(8 字段,trading_date 有夜盘日切语义)。
- 新增表:`universe/futures_instruments.parquet`(全合约基础信息)、`dominant2/dominant3/dominant_rule1`、`indices/commodity_indices.parquet`(中证 CFCI/CFI 等 35 个商品期货指数,2010 起)、`exchange_daily/<SYM>.parquet`(官方结算价),`continuous/`(近月/次月)、`roll_yield/`(米筐 carry)、`warehouse_stocks/`(补大商所)、`member_rank/`、`trading_parameters/`(保证金/手续费/限仓:SHFE 2013-10、DCE 2018-12、CZCE 2021-04 起)、`options/`(合约/主力月份/PCR/IV/skew,补 DCE 期权缺口)、`econ/`(全部 4006 个宏观因子,带发布时点 `info_date`)、`spot/`(上金所现货与早午盘基准价)。
- 覆盖范围:交易所口径的全部商品品种(中金所除外,90 个品种,含 2016 年后退市的合约),不再限于原导出的 23 个。`futures_tick/` 为可选抽样脚本,默认不跑(流量大)。
- 只含真实合约:合成连续合约(88/888/889/99/88A2,价格经平滑可为负)不进 `contracts_daily`/`futures_5minute`;连续价用 `dominant_daily/`、`continuous/` 或 `indices/`。

