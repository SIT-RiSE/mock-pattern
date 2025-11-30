import os
import json
import csv
from glob import glob


def analyze_mock_objects(json_path):
    """
    读取单个 JSON 文件，统计其中每个 mock object 的信息：
    - Project: 项目名（这里用文件名去掉扩展名）
    - MockID: rawMockObjectId
    - Dependency: variableType
    - MockLevel: mockPatternLevel
    - TestCount: 影响的测试用例数量（按 methodName 去重计数）
    - StubCount: stub 语句数量（type == "STUBBING"）
    """
    project_name = os.path.splitext(os.path.basename(json_path))[0]

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = []

    for obj in data:
        raw_mock_object_id = obj.get("rawMockObjectId")
        mock_pattern_level = obj.get("mockPatternLevel", 0)
        dependency = obj.get("variableType", "")


        # 统计测试用例 & stub 数量
        test_methods = set()   # 用于去重：每个测试方法只算一次
        stub_count = 0
        shared_stub_counted = 0  # 避免重复计数同一 stub 语句

        for statement in obj.get("statements", []):
            # 1) stub 语句数量
            if statement.get("type") == "STUBBING":
                stub_count += 1


            # 2) 判断是否属于测试用例
            location_context = statement.get("locationContext", {}) or {}
            locate = statement.get("locate", "")
            method_name = location_context.get("methodName", "") or ""
            method_annotations = location_context.get("methodAnnotations", []) or []

            is_test_case = (
                locate == "Test Case"
                or "Test" in method_annotations
                or "test" in method_name.lower()
            )

            if is_test_case:
                # 以 methodName 作为测试用例的标识；如果没名字就退回到行号
                test_id = method_name if method_name else f"line_{statement.get('line', -1)}"
                test_methods.add(test_id)
            else: 
                # 不是测试用例的话，检查是否是 shared stub                               
                shared_stub_counted += 1

        test_case_count = len(test_methods)

        # 如果你后面会拿 TestCount 做除法，不想出现 0，可以解开下面这行：
        if test_case_count == 0:
            if mock_pattern_level == 0:
                test_case_count = 1
            else:
                test_case_count = 2
        if shared_stub_counted > stub_count:
            shared_stub_counted = stub_count

        results.append({
            "Project": project_name,
            "MockID": raw_mock_object_id,
            "Dependency": dependency,
            "MockLevel": mock_pattern_level,
            "TestCount": test_case_count,
            "StubCount": stub_count,
            "SharedStubCount": shared_stub_counted,
        })

    return results


if __name__ == "__main__":
    # 获取所有 mock object 目录下的 json 文件
    json_files = glob(r"RQ 3\mock object\*.json")

    all_data = []
    for json_path in json_files:
        all_data.extend(analyze_mock_objects(json_path))

    # 导出为一个总的 CSV
    output_csv = "mock_object_summary.csv"
    fieldnames = ["Project", "MockID", "Dependency", "MockLevel", "TestCount", "StubCount", "SharedStubCount"]

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_data)

    print(f"写入 {len(all_data)} 行到 {output_csv}")
