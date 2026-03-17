# Replication Package: The Complexity Shield

**The Complexity Shield: Modeling and Measuring the Impact of Mock Sharing Patterns**  
Gengwu Zhao, Lu Xiao, Xinyi Li, and Sunny Wong  
Submitted to IEEE Transactions on Software Engineering, 2026

GitHub: https://github.com/SIT-RiSE/mock-pattern

---

## What this study is about

This study investigates how developers organize and reuse mocking logic in Java test code. We model mock sharing with three levels:

- **L0**: non-shared mocks defined locally in one test
- **L1**: fully shared mocks defined in shared setup/helper code
- **L2**: partially shared mocks with shared core logic and local extensions

Using 56,502 mock objects from 97 Apache projects, the study answers three questions:

- **RQ1**: How are L0/L1/L2 distributed across projects?
- **RQ2**: How do mock sharing levels evolve over time?
- **RQ3**: How does converting mocks between sharing levels affect test complexity (CCTR)?

---

## Package structure

```text
.
├── README.md
├── DATA.md                            ← column-level data dictionary
├── final_97_projects.csv              ← 97 projects used in the paper
├── mock-pattern-analyzer/             ← Java static analysis tool
├── RQ 1/                              ← distribution analysis
├── RQ 2/                              ← longitudinal trend analysis
└── RQ 3/                              ← CCTR conversion simulation
```

## Main data files

- `final_97_projects.csv` — the 97 projects used in the paper, with L0/L1/L2 breakdown
- `RQ 1/mock_object_summary.csv` — mock-level dataset for distribution analysis (59,447 rows, all 260 projects)
- `RQ 2/mock_trend_analysis_final.csv` — per-project trend classification results
- `RQ 3/CCTR_Conversion_Summary.csv` — simulated conversions and CCTR impact (23,350 rows)

Column definitions and supplementary file descriptions are in [`DATA.md`](DATA.md).

---

## Quick reproduction

Processed data is already included. The commands below reproduce the main analyses and figures directly.

```bash
# RQ1 — Distribution
cd "RQ 1" && python gen_fit.py

# RQ2 — Evolution
cd "RQ 2" && python get_trend.py

# RQ3 — Complexity impact
cd "RQ 3" && python gen_fig.py
```

### Requirements

- Python 3.9+
- `pip install pandas openpyxl scipy matplotlib pymannkendall tree-sitter tree-sitter-java`

---

## Static analysis tool

The `mock-pattern-analyzer/` directory contains a Java tool that extracts and classifies mock objects from Java test source code via AST parsing. A pre-built JAR is included:

```
mock-pattern-analyzer/target/mock-analyzer-1.0-jar-with-dependencies.jar
```

The JAR has two modes:

```bash
# pattern mode: classify each mock as L0/L1/L2, output one JSON per project
java -jar mock-analyzer-1.0-jar-with-dependencies.jar pattern <source_dir> <output.json>

# clone mode: analyze L0 mocks for upgrade simulation
java -jar mock-analyzer-1.0-jar-with-dependencies.jar clone <source_dir> <output.json>
```

The pre-parsed JSON files are already provided in `RQ 1/mock object/` and `RQ 3/cloned mock/`, so running the JAR is not required to reproduce the paper's results.

To rebuild from source (requires Java 11+, Maven 3.6+):

```bash
cd mock-pattern-analyzer && mvn package
```

---

## License

This package is provided for academic research purposes. The analyzed projects are open-source Apache Software Foundation projects under the Apache License 2.0.