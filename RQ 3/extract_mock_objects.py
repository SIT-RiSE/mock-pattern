import csv
import os
import shutil
import subprocess
import stat

CSV_FILE = r'C:\Users\10590\OneDrive - stevens.edu\PHD\2025 Fall\mock pattern\mock-pattern-analyzer\apache project list.csv'
TEMP_DIR = r'C:\Java_projects\temp_projects'
JAR_PATH = r'C:\Users\10590\OneDrive - stevens.edu\PHD\2025 Fall\mock pattern\mock-pattern-analyzer\target\mock-analyzer-1.0-jar-with-dependencies.jar'
OUTPUT_DIR = r'C:\Users\10590\OneDrive - stevens.edu\PHD\2025 Fall\mock pattern\RQ 3\cloned mock'
# Test_Jar_PATH = r'C:\Users\10590\OneDrive - stevens.edu\PHD\2025 Fall\mock pattern\test-parser-1.0-SNAPSHOT-jar-with-dependencies.jar'

def get_apache_projects(csv_file):
    projects = {}
    with open(csv_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            projects[row['project']] = row['repository']
    return projects

def run_command(cmd, cwd=None):
    print(f'Executing command: {" ".join(cmd)}')
    subprocess.run(cmd, check=True, cwd=cwd)

def clone_project(repo_url, dest_dir):
    run_command(['git', 'clone', repo_url, dest_dir])

def analyze_project(project_path, output_json, jar_path=JAR_PATH):
    run_command([
        'java', '-jar', jar_path,'clone' , project_path, output_json
    ])

def remove_project_dir(project_path):
    # Try to remove read-only files and handle permission errors
    def onerror(func, path, exc_info):
        if not os.access(path, os.W_OK):
            os.chmod(path, stat.S_IWUSR)
            func(path)
        else:
            print(f'Failed to remove {path}: {exc_info}')
    if os.path.exists(project_path):
        shutil.onexc(project_path, onerror=onerror)

def main():
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    projects = get_apache_projects(CSV_FILE)
    for name, repo in projects.items():
        print(f'Processing {name}...')
        project_path = os.path.join(TEMP_DIR, name.replace(' ', '_'))
        output_json = os.path.join(OUTPUT_DIR, f'{name.replace(" ", "_")}.json')
        test_output_json = os.path.join(OUTPUT_DIR.replace("mock object", "testcase"), f'{name.replace(" ", "_")}_test.json')

        # 如果项目未下载则先下载项目
        if not os.path.exists(project_path):
            try:
                clone_project(repo, project_path)
            except Exception as e:
                print(f'Error cloning {name}: {e}')
        else:
            print(f'{name} already cloned.')
       
        # 如果项目还没有分析mock则分析项目的mock
        if not os.path.exists(output_json):
            try:
                analyze_project(project_path, output_json)
            except Exception as e:
                print(f'Error analyzing {name} for mock object: {e}')
        else:
            print(f'JSON for {name} already exists.')
            
        # 如果项目还没有分析test case则分析项目的test case
        if not os.path.exists(test_output_json):
            try:
                analyze_project(project_path, test_output_json, Test_Jar_PATH)
            except Exception as e:
                print(f'Error analyzing {name} for test case: {e}')
        else:
            print(f'Test JSON for {name} already exists.')

        # 删除项目文件夹
        #remove_project_dir(project_path)
    print('All projects processed.')

if __name__ == '__main__':
    main()