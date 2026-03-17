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

OUTPUT_CSV = os.path.join(r"C:\CCTR\complexity_summary.csv")
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
        "instanceId": 1,
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
        instanceId = obj.get("instanceId")
        #如果parser没有成功的计算转换信息，默认由Level 0转换为Level 1.
        convertedLevel = obj.get("convertedLevel", 1)

        # 收集所有 test 方法代码，至少由2个测试用例执行
        test_case_count = obj.get("numberOfConverted", 2)
        raw_code = set()
        shared_code = obj.get("sharedLogic", "")
        for mock in obj.get("involvedMocks", []):
            stmts = mock.get("statements", [])
            # 只需要添加第一个语句所在的方法代码，因为Levl 0的其他语句应该在同一个方法内
            st_code = stmts[0].get("locationContext", {}).get("methodRawCode", "")
            if st_code:
                raw_code.add(st_code)

        # 拼接所有方法代码
        raw_code_text = "\n".join(raw_code)
        converted_code_text = shared_code + "\n" + raw_code_text
        rm_code = raw_code_text


        # 去除当前 mock object 的语句
        for mock in obj.get("involvedMocks", []):
            stmts = mock.get("statements", [])
            for stmt in stmts:
                st_code = stmt.get("code", "")
                st_type = stmt.get("type", "")
                st_stubbedMethod = stmt.get("stubbedMethod", "")
                if st_code:
                    rm_code = rm_code.replace(st_code, "")
                    if st_type == "CREATION" or (st_type == "STUBBING" and st_stubbedMethod in obj.get("coreStubbedMethods", [])):
                        converted_code_text = converted_code_text.replace(st_code, "")

        # 计算复杂度
        raw_code_cctr = CognitiveComplexityCalculatorTestAware(raw_code_text).compute_complexity()
        converted_code_cctr = CognitiveComplexityCalculatorTestAware(converted_code_text).compute_complexity()
        
        rm_code_cctr = CognitiveComplexityCalculatorTestAware(rm_code).compute_complexity()



        results.append({
            "Project": project_name,
            "InstanceID": instanceId,
            "Dependency": obj.get("variableType", 0),
            "L0Count": test_case_count,
            "ConvertedLevel": convertedLevel,
            "RawCCTR": raw_code_cctr,
            "AddedCCTR": raw_code_cctr - rm_code_cctr,
            "ConvertedCCTR": converted_code_cctr - rm_code_cctr,
            "CCTRReduction": (raw_code_cctr - converted_code_cctr),
            "AddedCCTRPerTest": (raw_code_cctr - rm_code_cctr) / test_case_count if test_case_count > 0 else 0,
            "ConvertedAddedCCTRPerTest": (converted_code_cctr - rm_code_cctr) / test_case_count if test_case_count > 0 else 0,
            "CCTRReductionPerTest": (raw_code_cctr - converted_code_cctr) / test_case_count if test_case_count > 0 else 0
        })

    return results


# 获取所有 mock object 目录下的 json 文件
json_files = glob(r"cloned mock\*.json")

all_data = []
for json_path in json_files:
    result = analyze_mock_objects(json_path)
    all_data.extend(result)

df = pd.DataFrame(all_data)
df.to_csv('L0_conversion_result.csv', index=False)

