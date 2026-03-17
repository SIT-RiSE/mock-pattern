# Data Dictionary

Column-level descriptions for all datasets in this replication package.

---

## `final_97_projects.csv`

The 97 Apache projects analyzed in the paper, filtered from 260 candidates by requiring ≥10 Mockito mock objects.

| Column | Description |
|--------|-------------|
| `Project` | Apache project name |
| `TotalMocks` | Total mock objects in the project |
| `L0_Count` / `L0_Ratio` | Number and proportion of L0 (non-shared) mocks |
| `L1_Count` / `L1_Ratio` | Number and proportion of L1 (fully shared) mocks |
| `L2_Count` / `L2_Ratio` | Number and proportion of L2 (partially shared) mocks |

---

## RQ 1: Distribution

### `RQ 1/mock_object_summary.csv`

Primary dataset. One row per mock object across all 260 projects (59,447 rows). The paper uses the 97-project subset from `final_97_projects.csv`.

| Column | Description |
|--------|-------------|
| `Project` | Apache project name |
| `MockID` | Unique mock identifier |
| `Dependency` | Mocked class type |
| `MockLevel` | 0 (L0), 1 (L1), or 2 (L2) |
| `TestCount` | Number of test methods using this mock |
| `StubCount` | Total stub statements |
| `SharedStubCount` | Stubs located in shared setup code |

### Other files in `RQ 1/`

| File | Description |
|------|-------------|
| `mock object/` | Raw per-project JSON files (243 projects), output of the analyzer |
| `testcase/` | Per-project test case data |
| `mock lifecycle.xlsx` | Mock lifecycle analysis workbook |
| `stats_output.csv.xlsx` | Per-project aggregated statistics |
| `project_size_report.csv` | Project size metrics (LOC, classes, methods) for 258 projects |
| `project_report.xlsx` | Combined project-level report |
| `exact_mock.py` | Extracts mocks from JSON → `mock_object_summary.csv` |
| `gen_fit.py` | Generates RQ1 distribution figures |
| `collect_mock_level_by_test.py` | Aggregates mock levels per test method |
| `project_size_factor.py` | Computes project size factors |
| `project_git_cycle_and_tloc.py` | Git activity cycle and test LOC metrics |

---

## RQ 2: Evolution

### `RQ 2/mock_trend_analysis_final.csv`

Per-project trend classification (110 projects).

| Column | Description |
|--------|-------------|
| `Project` | Project name |
| `Slope` | Mann-Kendall slope estimate |
| `P-value` | Statistical significance |
| `R²` | Coefficient of determination |
| `Trend` | Stable / Increasing / Decreasing / Fluctuating |

### `RQ 2/mock_trend_analysis.xlsx`

Yearly L0 ratio matrix: 14 year-rows × 110 project-columns. Each cell is L0/(L0+L1+L2) for that project in that year.

### `RQ 2/mock_trend_by_project.xlsx`

Detailed yearly time series. Each project has three columns: `{Project}_Year`, `{Project}_Level0/Total` (fraction string, e.g. "17/33"), `{Project}_Percentage` (float).

### Other files in `RQ 2/`

| File | Description |
|------|-------------|
| `mock_trend_analysis_stat.csv` | Summary counts of trend distribution |
| `get_trend.py` | Mann-Kendall trend test → `mock_trend_analysis_final.csv` |
| `get_trend_extended.py` | Extended version with additional statistical tests |
| `export_mock_trend_excel.py` | Exports trend data to Excel format |

---

## RQ 3: Complexity Impact

### `RQ 3/CCTR_Conversion_Summary.csv`

Simulated mock-level conversions (23,350 rows). Each row is one conversion event.

| Column | Description |
|--------|-------------|
| `Project` | Project name |
| `FromLevel` | Original mock level (0, 1, or 2) |
| `ToLevel` | Target mock level after conversion |
| `CCTRReduction` | CCTR change (negative = reduced complexity) |
| `CCTRReductionPerTest` | Per-test CCTR change |
| `ReductionRatio` | Relative change: (after − before) / before |

Note: files store CCTR deltas, not absolute before/after values.

### `RQ 3/CCTR_Conversion_Summary-fixed.xlsx`

Same data as the CSV above, with additional `TestCount` column and split into sheets:

| Sheet | Rows | Description |
|-------|------|-------------|
| `CCTR_Conversion_Summary` | 23,350 | All conversions |
| `Sheet1` | 6,951 | Upgrades only (L0→L1/L2) |
| `Sheet2` | 16,399 | Downgrades only (L1/L2→L0) |

### `RQ 3/CCTR_project_summary.xlsx`

Project-level aggregated summaries:

| Sheet | Rows | Description |
|-------|------|-------------|
| `Sheet3` | 6,951 | Upgrade detail with ECDF coordinates |
| `Sheet4` | 8,255 | Downgrade detail (subset) with ECDF coordinates |
| `Sheet5` | 98 | Per-project average downgrade reduction ratio |
| `Sheet6` | 92 | Per-project ECDF two-point summary |
| `Sheet7` | 94 | Project-level upgrade/downgrade counts |

### `RQ 3/non_shared_ecdf.csv` and `RQ 3/shared_ecdf.csv`

Pre-computed ECDF coordinates for RQ3 figures. Used directly by `gen_fig.py`.

| Column | Description |
|--------|-------------|
| `ecdf_x` | CCTR reduction ratio value |
| `ecdf_y` | Cumulative probability |

`non_shared_ecdf.csv`: 6,951 upgrade events. `shared_ecdf.csv`: 8,255 downgrade events (filtered subset; full 16,399 downgrades are in `CCTR_Conversion_Summary-fixed.xlsx` Sheet2).

### `RQ 3/L0_conversion_result.csv`

Per-mock L0 conversion results (6,951 rows).

| Column | Description |
|--------|-------------|
| `Project` | Apache project name |
| `InstanceID` | Mock clone instance identifier |
| `Dependency` | Mocked class type |
| `L0Count` | Number of L0 mocks in the conversion group |
| `ConvertedLevel` | Target level (1 or 2) |
| `RawCCTR` | Original CCTR before conversion |
| `AddedCCTR` | CCTR added by mock configuration |
| `ConvertedCCTR` | CCTR after conversion |
| `CCTRReduction` | Absolute CCTR change |
| `CCTRReductionPerTest` | Per-test CCTR reduction |

### `RQ 3/result.csv`

Raw per-mock CCTR calculation output (59,447 rows). The foundational dataset from which all RQ3 analyses are derived.

### Other files in `RQ 3/`

| File | Description |
|------|-------------|
| `test-suite.csv` | Test file complexity metrics (simulation input) |
| `L0_conversion_summary.csv` | Average CCTR summary for L0→L1 and L0→L2 (2 rows) |
| `CCTR_Level_Summary.csv` | Average CCTR per mock level (3 rows) |
| `CCTR_Conversion_Group_Summary.csv` | Stats per conversion direction (4 rows) |
| `cctr.py` | CCTR calculation engine |
| `CCTR-convertedLevel.py` | Conversion simulation script |
| `conversion_updated.py` | Updated conversion logic |
| `extract_mock_objects.py` | Mock object extraction for RQ3 input |
| `mock_cctr_summary_generator.py` | Per-project CCTR summary generator |
| `gen_fig.py` | Generates ECDF figures for RQ3 |
| `mock object/` | Per-project mock object JSON (RQ3 subset) |
| `cloned mock/` | Mock clone instance data from simulation |
