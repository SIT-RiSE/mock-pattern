import os
from tree_sitter import Language, Parser
import tree_sitter_java as tsjava
import pandas as pd
import json
import os

from glob import glob

# === Tree-sitter Java Initialization ===
JAVA_LANGUAGE = Language(tsjava.language())
parser = Parser(JAVA_LANGUAGE)

# # === Resource Paths ===
# SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# OUTPUT_CSV = os.path.join(r"C:\CCTR\complexity_summary.csv")
# os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

# === Test-Aware Cognitive Complexity Calculator ===
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


def analyze_mock_objects(json_path):
    """
    分析指定 JSON 文件中每个 mock object 对测试复杂度 (CCTR) 的影响。

    输出：
    [
      {
        "project_name": "ActiveMQ",
        "rawMockObjectId": 1,
        "mockPatternLevel": 0,
        "added_cctr": 12.0,
        "avg_added_cctr_per_test_case": 6.0,
        "raw_code_cctr": 34.0,
        "re_mo_code_cctr": 22.0,
        "test_case_count": 2
      },
      ...
    ]
    """
    project_name = os.path.splitext(os.path.basename(json_path))[0]
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = []

    for obj in data:
        rawMockObjectId = obj.get("rawMockObjectId")
        mockPatternLevel = obj.get("mockPatternLevel", 0)

        # 收集所有 test 方法代码
        test_case_count = 0
        raw_code = set()
        shared_code = set()
        for statement in obj.get("statements", []):
            locationContext = statement.get("locationContext", {})
            method_code = locationContext.get("methodRawCode", "")
            if statement.get("isShared", True) and statement.get("type", "") != "REFERENCE" and statement.get("type", "") != "VERIFICATION" :
                shared_code.add(statement.get("code", ""))
            if not method_code:
                continue
            if method_code not in raw_code:
                raw_code.add(method_code)
                if (statement.get("locate", "") == "Test Case" or
                    "Test" in locationContext.get("methodAnnotations", []) or
                    "test" in locationContext.get("methodName", "").lower()):
                    test_case_count += 1




        # 拼接所有方法代码
        raw_code_text = "\n".join(raw_code)
        re_mo_code_text = raw_code_text

        if mockPatternLevel == 0:
            added_mo_code = raw_code_text
        else:
            added_mo_code = ""
            for test in raw_code:
                code_to_add = test
                for shared in shared_code:
                    if shared not in test:
                        code_to_add += "\n" + shared
                added_mo_code += code_to_add + "\n"
            added_mo_code = added_mo_code.strip()

        if mockPatternLevel == 0:
            test_case_count = 1
        elif test_case_count == 0:
            test_case_count = 2  # 避免除以零
        
        

        # 去除当前 mock object 的语句
        for statement in obj.get("statements", []):
            st_code = statement.get("code", "")
            if st_code:
                re_mo_code_text = re_mo_code_text.replace(st_code, "")

        # 计算复杂度
        raw_code_cctr = CognitiveComplexityCalculatorTestAware(raw_code_text).compute_complexity()
        re_mo_code_cctr = CognitiveComplexityCalculatorTestAware(re_mo_code_text).compute_complexity()
        added_mo_code_cctr = CognitiveComplexityCalculatorTestAware(added_mo_code).compute_complexity()

        added_cctr = raw_code_cctr - re_mo_code_cctr
        avg_added_cctr = added_cctr / test_case_count if test_case_count > 0 else 0.0

        tranformed_cctr = added_mo_code_cctr - re_mo_code_cctr
        avg_tranformed_cctr = tranformed_cctr / test_case_count if test_case_count > 0 else 0.0

        results.append({
            "Project": project_name,
            "MockID": rawMockObjectId,            
            "Dependency": obj.get("variableType", 0),
            "MockLevel": mockPatternLevel,            
            "TestCount": test_case_count,
            "AvgAddedCCTR": avg_added_cctr,
            "Level0CCTR": avg_tranformed_cctr,
            "RawCCTR": raw_code_cctr,
            "NoMockCCTR": re_mo_code_cctr,
            "AddedCCTR": added_cctr,
        })

    return results


# 获取所有 mock object 目录下的 json 文件
json_files = glob(r"mock object\*.json")

all_data = []
for json_path in json_files:
    result = analyze_mock_objects(json_path)
    all_data.extend(result)

df = pd.DataFrame(all_data)
df.to_csv('result.csv', index=False)

# 确保关键列为数值类型
numeric_cols = ["TestCount", "AvgAddedCCTR", "AddedCCTR"]
df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")

# 按 MockLevel 分组聚合
summary = df.groupby("MockLevel").agg(
    MockObjectCount=("MockID", "count"),
    TotalTestCount=("TestCount", "sum"),
    AvgTestPerMock=("TestCount", "mean"),               # 平均每个 Mock 影响的测试数
    AvgAddedCCTR_perTest=("AvgAddedCCTR", "mean"),      # 平均每个测试增加的复杂度
    AvgAddedCCTR_perMock=("AddedCCTR", "mean")          # 平均每个 Mock 增加的复杂度
).reset_index()

# 输出结果
print(summary)

# 可选：保存到 CSV
summary.to_csv("CCTR_Level_Summary.csv", index=False)

