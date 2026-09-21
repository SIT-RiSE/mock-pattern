# mock-pattern v2 全量结果

用 mock-pattern v2（`mock-pattern-analyzer/V2.md`）对 `apache project list.csv` 中 260 个项目各自默认分支最新 commit 的运行结果。不编译被测项目，不使用 LLM。运行日期 2026-09-21/22。

- `summary.csv`：每个项目一行（commit、mock 数、L0/L1/L2、MCI 数、减少的 mock 数与 stub 数、耗时）。
- `unavailable-projects.csv`：17 个 GitHub 上已不存在的退役项目（旧数据里同样没有它们）。
- `projects/<项目>/`：`summary.json`、`mock-objects.json`（每个 mock 的分级）、`excluded.json`（被排除的 spy 和无创建语句变量）、`run.json`。
- `mci.json`（MCI 详情，含完整方法源码，共约 457MB）没有放进仓库，压缩包在 `D:/Java_projects/mock-pattern-v2/archive/mci-json.zip`（18MB）。

## 概况
243/260 个项目运行成功；其中 124 个至少有 1 个 mock，103 个有 ≥10 个 mock（论文筛选标准）。共 79,850 个 mock（L0 53,645 / L1 17,683 / L2 8,522），10,500 个 MCI，理论上可减少 29,072 个 mock；stub 语句可减少 21,633（精确口径）到 32,166（抽象口径）条。

## 注意
- 扫描阶段有 352 个文件解析失败（占总文件数很小），较集中的是 Drill（106/4801）、NetBeans（73/39097）、Camel（31/26977）。
- 各项目的 commit 不同，源码保存在 `D:/Java_projects/mock-pattern-v2/sources/`（blobless 克隆，含完整提交历史，供 RQ2 年度快照使用）。
