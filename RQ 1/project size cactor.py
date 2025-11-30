import os
import re
import csv

# 你的根目录，里面包含 200+ 个项目，每个文件夹名就是项目名
ROOT_DIR = "C:\\Java_projects\\temp_projects"

# 输出结果 csv
OUTPUT_FILE = "project_size_report.csv"

# 用正则匹配 class/interface/enum/method
CLASS_PATTERN = re.compile(r"\b(class|interface|enum)\s+\w+")
METHOD_PATTERN = re.compile(r"\b(public|private|protected)?\s+[\w<>\[\]]+\s+\w+\s*\(")

def count_project_size(project_path):
    java_files = []
    class_count = 0
    method_count = 0
    total_loc = 0
    java_loc = 0

    for root, _, files in os.walk(project_path):
        for file in files:
            file_path = os.path.join(root, file)

            # 统计总行数
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                total_loc += len(lines)
            except:
                continue

            # 如果不是 .java 就跳过 class/method 统计
            if not file.endswith(".java"):
                continue

            java_files.append(file_path)
            java_loc += len(lines)

            # 统计 class 和 method
            content = "".join(lines)
            class_count += len(re.findall(CLASS_PATTERN, content))
            method_count += len(re.findall(METHOD_PATTERN, content))

    return {
        "java_file_count": len(java_files),
        "class_count": class_count,
        "method_count": method_count,
        "total_loc": total_loc,
        "java_loc": java_loc,
    }

def main():
    projects = [d for d in os.listdir(ROOT_DIR) if os.path.isdir(os.path.join(ROOT_DIR, d))]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["project", "java_files", "classes", "methods", "total_loc", "java_loc"])

        for project in sorted(projects):
            print(f"Processing {project} ...")
            project_path = os.path.join(ROOT_DIR, project)
            stats = count_project_size(project_path)

            writer.writerow([
                project,
                stats["java_file_count"],
                stats["class_count"],
                stats["method_count"],
                stats["total_loc"],
                stats["java_loc"],
            ])

    print(f"\nDone! Output saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
