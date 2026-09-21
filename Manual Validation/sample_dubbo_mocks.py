"""
任务一：从 Dubbo 项目里随机抽 100 个 mock object，导出可追溯、可人工标记的表格。

数据源：`RQ 1/mock object/Dubbo.json`（与 RQ 3/mock object 内容一致）。
每行对应一个 mock object，附上变量名、涉及的测试用例名、文件路径等定位信息，
方便回溯到原始 JSON 里对应的 rawMockObjectId。
"""

import json
import os
import random

import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
DUBBO_JSON = os.path.join(ROOT_DIR, "RQ 1", "mock object", "Dubbo.json")

SEED = 42
SAMPLE_SIZE = 100


def is_test_statement(stmt):
    loc_ctx = stmt.get("locationContext", {})
    return (
        stmt.get("locate") == "Test Case"
        or "Test" in loc_ctx.get("methodAnnotations", [])
        or "test" in loc_ctx.get("methodName", "").lower()
    )


def extract_row(sample_id, obj):
    statements = obj.get("statements", [])
    test_case_names = sorted({
        s.get("locationContext", {}).get("methodName", "")
        for s in statements
        if is_test_statement(s) and s.get("locationContext", {}).get("methodName")
    })
    stub_count = sum(1 for s in statements if s.get("type") == "STUBBING")
    class_ctx = obj.get("classContext", {})

    return {
        "SampleID": f"S{sample_id:03d}",
        "Project": "Dubbo",
        "rawMockObjectId": obj.get("rawMockObjectId"),
        "mockPatternLevel": obj.get("mockPatternLevel"),
        "variableName": obj.get("variableName", ""),
        "variableType": obj.get("variableType", ""),
        "isGlobal": obj.get("isGlobal", False),
        "packageName": class_ctx.get("packageName", ""),
        "className": class_ctx.get("className", ""),
        "filePath": class_ctx.get("filePath", ""),
        "testCaseNames": "; ".join(test_case_names),
        "testCaseCount": len(test_case_names),
        "stubCount": stub_count,
        "statementCount": len(statements),
        "ManualNote": "",
    }


def main():
    with open(DUBBO_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    rng = random.Random(SEED)
    n = min(SAMPLE_SIZE, len(data))
    sampled = rng.sample(data, n)

    rows = [extract_row(i + 1, obj) for i, obj in enumerate(sampled)]
    df = pd.DataFrame(rows)

    out_path = os.path.join(SCRIPT_DIR, "dubbo_mock_sample.xlsx")
    df.to_excel(out_path, index=False)
    print(f"Wrote {len(df)} rows to {out_path}")
    print(df["mockPatternLevel"].value_counts())


if __name__ == "__main__":
    main()
