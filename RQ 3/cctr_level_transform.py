"""
统一计算两个方向的 mock 等级变换对 CCTR (Cognitive Complexity of Test-related code) 的影响。
方向命名与 Mock_Pattern_TSE.pdf（Section III-C）保持一致，使用论文里的 Upgrade / Downgrade 术语：

  方向一：Upgrade  (L0 -> L1/L2)
    数据源：`cloned mock/<Project>.json`
    每个 cluster 是若干个 Level 0 克隆 mock 实例 (involvedMocks) 被合并成一份共享逻辑 (sharedLogic)。
    before = 升级前，每个克隆实例各自所在测试方法的原始代码
    after  = 升级后，每个测试方法自己去掉已经被吸收进 sharedLogic 的 CREATION / 核心
             STUBBING 语句（不拼接 sharedLogic 本身——CCTR 只看单个测试用例自己的方法体，
             不是整个 test suite，sharedLogic 是独立于每个测试用例之外的一次性开销）

  方向二：Downgrade  (L1/L2 -> L0)
    数据源：`RQ 1/mock object/<Project>.json`，只看 mockPatternLevel 为 1 或 2 的 mock object
    before = 降级前，该 mock 涉及的每个测试用例方法的原始代码（共享的创建/打桩语句
             并不在方法体内，而是在字段声明或 @Before 里）
    after  = 降级后，把该 mock object 里 isShareable == True 的语句代码，逐一塞进每个
             测试用例方法（如果测试用例里还没有这段代码的话），模拟"每个测试各自
             创建/打桩一份"

两个方向各自输出 before/after 的 CCTR 与差值，写入同一份结果表，用 Direction/FromLevel/ToLevel
区分。Direction 只有 Upgrade/Downgrade 两个值（不区分目标是 L1 还是 L2），细分等级请看
FromLevel/ToLevel 列。

输出三份文件：
  cctr_level_transform_result.csv          逐条 mock 记录明细
  cctr_level_transform_summary.csv         按 Direction + FromLevel + ToLevel 细分汇总（0->1 与 0->2 分开）
  cctr_level_transform_summary_overall.csv 按 Direction 汇总的整体 Upgrade / Downgrade 结果（0->1 与 0->2 合并）
"""

import json
import os
from glob import glob

import pandas as pd
from tree_sitter import Language, Parser
import tree_sitter_java as tsjava

JAVA_LANGUAGE = Language(tsjava.language())
parser = Parser(JAVA_LANGUAGE)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
CLONED_MOCK_DIR = os.path.join(SCRIPT_DIR, "cloned mock")
MOCK_OBJECT_DIR = os.path.join(ROOT_DIR, "RQ 1", "mock object")


class CognitiveComplexityCalculatorTestAware:
    def __init__(self, code, method_name=None):
        self.code = code.encode("utf-8")
        self.method_name = method_name
        self.complexity = 0
        self.nesting_level = 0
        self.parser = parser

    def compute_complexity(self):
        tree = self.parser.parse(self.code)
        self._analyze_node(tree.root_node)
        return self.complexity

    def _analyze_node(self, node):
        for child in node.children:
            kind = child.type
            text = self.code[child.start_byte:child.end_byte].decode("utf-8")
            if kind in ["if_statement", "for_statement", "while_statement", "do_statement", "switch_statement", "catch_clause"]:
                self._increment(child)
            elif kind == "binary_expression" and ("&&" in text or "||" in text):
                self.complexity += 1
            elif kind == "labeled_statement" and any(k in text for k in ["break", "continue", "goto"]):
                self.complexity += 1
            elif kind == "method_invocation":
                if self._is_recursive_call(text):
                    self.complexity += 1
                if any(x in text for x in ["mock(", "when(", "verify("]):
                    self.complexity += 1
                if "assert" in text or "fail(" in text:
                    self.complexity += 1
            elif kind == "annotation":
                if "@Test" in text:
                    self.complexity += 1
                elif "@ParameterizedTest" in text:
                    self.complexity += 2
                elif "@BeforeEach" in text or "@AfterEach" in text:
                    self.complexity += 1
            self._analyze_node(child)

    def _increment(self, node):
        self.complexity += 1 + self.nesting_level
        self.nesting_level += 1
        self._analyze_node(node)
        self.nesting_level -= 1

    def _is_recursive_call(self, text):
        return self.method_name and self.method_name in text


def compute_cctr(code_text):
    return CognitiveComplexityCalculatorTestAware(code_text).compute_complexity()


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []


# ---------------------------------------------------------------------------
# 方向一：Upgrade, L0 -> L1/L2
# ---------------------------------------------------------------------------
def analyze_upgrade_cluster(project_name, cluster):
    involved = cluster.get("involvedMocks", [])
    if not involved:
        return None

    raw_methods = []
    seen = set()
    for mock in involved:
        stmts = mock.get("statements", [])
        if not stmts:
            continue
        # Level 0 的一个 mock 实例，所有语句都在同一个方法内，取第一条语句所在方法即可
        method_code = stmts[0].get("locationContext", {}).get("methodRawCode", "")
        if method_code and method_code not in seen:
            seen.add(method_code)
            raw_methods.append(method_code)

    if not raw_methods:
        return None

    raw_code_text = "\n".join(raw_methods)

    # 注意 1：删除必须只作用于每个原始测试方法自己的文本，不能对拼接了 sharedLogic 之后的
    # 整个大字符串做全局 replace——sharedLogic 本身就是由这些被合并的语句生成的，
    # 如果在合并后的大字符串上整体删，会把 sharedLogic 刚生成出来的内容也一并删掉，
    # 人为地把"合并后"状态的复杂度算低。
    # 注意 2：CCTR 关注的是单个测试用例自己的方法体，不是整个 test suite。升级后，
    # sharedLogic（共享字段/helper 方法）本身不属于任何一个测试方法的方法体，
    # 所以不应该把它的内容计入"升级后"这个测试用例自己的 CCTR——它是一次性的、
    # 独立于每个测试用例之外的开销，不是某个具体测试用例读起来的复杂度。
    core_stubbed = set(cluster.get("coreStubbedMethods", []))
    cleaned_methods = []
    for method_code in raw_methods:
        cleaned = method_code
        for mock in involved:
            for stmt in mock.get("statements", []):
                code = stmt.get("code", "")
                if not code:
                    continue
                stype = stmt.get("type", "")
                is_core = stype == "CREATION" or (stype == "STUBBING" and stmt.get("stubbedMethod", "") in core_stubbed)
                if is_core:
                    cleaned = cleaned.replace(code, "")
        cleaned_methods.append(cleaned)

    converted_code_text = "\n".join(cleaned_methods)

    before_cctr = compute_cctr(raw_code_text)
    after_cctr = compute_cctr(converted_code_text)
    test_count = len(raw_methods)

    return {
        "Project": project_name,
        "Direction": "Upgrade",
        "ObjectId": cluster.get("instanceId"),
        "Dependency": involved[0].get("variableType", ""),
        "FromLevel": 0,
        "ToLevel": cluster.get("convertedLevel", 1),
        "InputMockCount": len(involved),
        "OutputMockCount": 1,
        "TestCount": test_count,
        "BeforeCCTR": before_cctr,
        "AfterCCTR": after_cctr,
        "CCTRChange": after_cctr - before_cctr,
        "CCTRChangePerTest": (after_cctr - before_cctr) / test_count if test_count else 0.0,
        "PctChange": (after_cctr - before_cctr) / before_cctr if before_cctr else None,
    }


def run_upgrade_direction():
    rows = []
    for json_path in glob(os.path.join(CLONED_MOCK_DIR, "*.json")):
        project_name = os.path.splitext(os.path.basename(json_path))[0]
        for cluster in load_json(json_path):
            row = analyze_upgrade_cluster(project_name, cluster)
            if row:
                rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# 方向二：Downgrade, L1/L2 -> L0
# ---------------------------------------------------------------------------
def analyze_downgrade_object(project_name, obj):
    statements = obj.get("statements", [])
    # 注意：字段名是 isShareable，不是 isShared
    shareable_codes = [s.get("code", "") for s in statements if s.get("isShareable") and s.get("code")]
    if not shareable_codes:
        return None

    test_methods = set()
    for s in statements:
        if s.get("locate") != "Test Case":
            continue
        method_code = s.get("locationContext", {}).get("methodRawCode", "")
        if method_code:
            test_methods.add(method_code)

    if not test_methods:
        return None

    raw_code_text = "\n".join(test_methods)

    split_parts = []
    for test in test_methods:
        piece = test
        for shared in shareable_codes:
            if shared not in piece:
                piece += "\n" + shared
        split_parts.append(piece)
    split_code_text = "\n".join(split_parts)

    before_cctr = compute_cctr(raw_code_text)
    after_cctr = compute_cctr(split_code_text)
    test_count = len(test_methods)

    return {
        "Project": project_name,
        "Direction": "Downgrade",
        "ObjectId": obj.get("rawMockObjectId"),
        "Dependency": obj.get("variableType", ""),
        "FromLevel": obj.get("mockPatternLevel"),
        "ToLevel": 0,
        "InputMockCount": 1,
        "OutputMockCount": test_count,
        "TestCount": test_count,
        "BeforeCCTR": before_cctr,
        "AfterCCTR": after_cctr,
        "CCTRChange": after_cctr - before_cctr,
        "CCTRChangePerTest": (after_cctr - before_cctr) / test_count if test_count else 0.0,
        "PctChange": (after_cctr - before_cctr) / before_cctr if before_cctr else None,
    }


def run_downgrade_direction():
    rows = []
    for json_path in glob(os.path.join(MOCK_OBJECT_DIR, "*.json")):
        project_name = os.path.splitext(os.path.basename(json_path))[0]
        for obj in load_json(json_path):
            if obj.get("mockPatternLevel") not in (1, 2):
                continue
            row = analyze_downgrade_object(project_name, obj)
            if row:
                rows.append(row)
    return rows


# ---------------------------------------------------------------------------
def _aggregate(df, group_cols):
    g = df.groupby(group_cols).apply(
        lambda x: pd.Series({
            "RecordCount": x["ObjectId"].count(),
            "TotalInputMocks": x["InputMockCount"].sum(),
            "TotalOutputMocks": x["OutputMockCount"].sum(),
            "AvgTestCount": x["TestCount"].mean(),
            "AvgCCTRChange": x["CCTRChange"].mean(),
            "AvgCCTRChangePerTest": x["CCTRChangePerTest"].mean(),
            "AvgPctChange": x["PctChange"].mean(),
            "WeightedPctChange": x["CCTRChange"].sum() / x["BeforeCCTR"].sum() if x["BeforeCCTR"].sum() else None,
        }),
        include_groups=False,
    ).reset_index()
    return g


def main():
    rows = run_upgrade_direction() + run_downgrade_direction()

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(SCRIPT_DIR, "cctr_level_transform_result.csv"), index=False)

    # 细分汇总：0->1 与 0->2（以及 1->0 与 2->0）分开统计
    detailed_summary = _aggregate(df, ["Direction", "FromLevel", "ToLevel"])
    detailed_summary.to_csv(os.path.join(SCRIPT_DIR, "cctr_level_transform_summary.csv"), index=False)

    # 整体汇总：Upgrade（0->1 和 0->2 合并）vs Downgrade（1->0 和 2->0 合并）
    overall_summary = _aggregate(df, ["Direction"])
    overall_summary.to_csv(os.path.join(SCRIPT_DIR, "cctr_level_transform_summary_overall.csv"), index=False)

    print("=== Detailed (by FromLevel/ToLevel) ===")
    print(detailed_summary)
    print()
    print("=== Overall (Upgrade vs Downgrade) ===")
    print(overall_summary)


if __name__ == "__main__":
    main()
