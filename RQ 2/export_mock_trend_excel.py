import os
import json
import datetime
import warnings
import pandas as pd


# ---------------------------
# 数据读取
# ---------------------------
def analyze_mock_file(mock_path):
    with open(mock_path, 'r', encoding='utf-8') as f:
        mock_data = json.load(f)
    mock_count = len(mock_data)
    level0 = sum(1 for obj in mock_data if obj.get('mockPatternLevel', None) == 0)
    return {
        'mock_object_count': mock_count,
        'mock_pattern_level_0': level0
    }


def collect_past_10_years_data(dir_path):
    project_name = os.path.basename(os.path.normpath(dir_path))
    try:
        all_files = [f for f in os.listdir(dir_path)
                     if f.endswith('.json') and f.startswith(project_name + '-')]
    except FileNotFoundError:
        return []

    current_year = datetime.datetime.now().year
    years = range(current_year - 9, current_year + 1)
    results = []

    for year in years:
        candidates = []
        for fname in all_files:
            suffix = fname[len(project_name) + 1:-5]
            parts = suffix.split('-', 1)
            if len(parts) != 2:
                continue
            try:
                y = int(parts[0])
                m = int(parts[1])
            except ValueError:
                continue
            if y == year:
                candidates.append((m, fname))

        if not candidates:
            continue

        latter = [c for c in candidates if 7 <= c[0] <= 12]
        if latter:
            chosen_fname = max(latter, key=lambda x: x[0])[1]
        else:
            first = [c for c in candidates if 1 <= c[0] <= 6]
            if not first:
                continue
            chosen_fname = max(first, key=lambda x: x[0])[1]

        chosen_path = os.path.join(dir_path, chosen_fname)
        stats = analyze_mock_file(chosen_path)
        total = stats['mock_object_count']
        level0 = stats['mock_pattern_level_0']
        percentage = round((level0 / total), 4) if total > 0 else 0.0
        results.append({
            'year': year,
            'level0_ratio': f'{level0}/{total}',
            'percentage': percentage
        })

    results.sort(key=lambda x: x['year'])
    return results


# ---------------------------
# 主分析函数：输出 Excel
# ---------------------------
def analyze_mock_stats(base_dir, output_excel):
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    all_projects_data = {}

    for project_name in os.listdir(base_dir):
        project_path = os.path.join(base_dir, project_name)
        if not os.path.isdir(project_path):
            continue

        data = collect_past_10_years_data(project_path)
        if not data:
            continue

        # 排除少于 2 年 或 全为 0% 的项目
        percentages = [d['percentage'] for d in data]
        if len(data) < 2 or all(p == 0 for p in percentages):
            continue

        all_projects_data[project_name] = data
        print(f"[{project_name}] {len(data)} years of data collected.")

    if not all_projects_data:
        print("[WARN] No valid project data found (all filtered out).")
        return

    # 构造表格
    all_years = sorted({d['year'] for proj in all_projects_data.values() for d in proj})
    df = pd.DataFrame({'Year': all_years})

    for proj, data in all_projects_data.items():
        year_map = {d['year']: d for d in data}
        df[f'{proj}_Year'] = [year if year in year_map else "" for year in all_years]
        df[f'{proj}_Level0/Total'] = [year_map[year]['level0_ratio'] if year in year_map else "" for year in all_years]
        df[f'{proj}_Percentage'] = [year_map[year]['percentage'] if year in year_map else "" for year in all_years]

    # 输出 Excel
    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='MockStats')

    print(f"[DONE] Excel file saved → {output_excel}")


# 示例运行
if __name__ == "__main__":
    analyze_mock_stats(r'output\\mock_object_by_year', 'mock_trend_by_project.xlsx')
