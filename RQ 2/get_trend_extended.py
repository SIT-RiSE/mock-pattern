import os
import csv
import json
import datetime
import warnings
from collections import Counter

import numpy as np
import matplotlib.pyplot as plt
import statsmodels.api as sm


# ---------------------------
# 数据读取（保持你的实现风格）
# ---------------------------
def analyze_mock_file(mock_path):
    with open(mock_path, 'r', encoding='utf-8') as f:
        mock_data = json.load(f)
    mock_count = len(mock_data)
    mock_pattern_level_dist = {}
    for obj in mock_data:
        level = obj.get('mockPatternLevel', None)
        mock_pattern_level_dist[level] = mock_pattern_level_dist.get(level, 0) + 1
    return {
        'mock_object_count': mock_count,
        'mock_pattern_level_0': mock_pattern_level_dist.get(0, 0),
        'mock_pattern_level_1': mock_pattern_level_dist.get(1, 0),
        'mock_pattern_level_2': mock_pattern_level_dist.get(2, 0),
        'mock_pattern_level_3': mock_pattern_level_dist.get(3, 0),
    }


def collect_past_10_years_percentages(dir_path):
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
        total = stats.get('mock_object_count', 0)
        level0 = stats.get('mock_pattern_level_0', 0)
        percentage = round((level0 / total), 4) if total > 0 else 0.0
        results.append({'year': year, 'percentage': percentage})

    results.sort(key=lambda x: x['year'])
    return results


# ---------------------------
# 主分析：以线性为主；不显著再试对数/指数/幂
# ---------------------------
def analyze_mock_trend(base_dir, output_csv):
    """
    以线性趋势为主：优先线性 OLS（真实年份）；若线性不显著（p>=α），
    依次尝试 Log / Exp / Power；添加 PValue 行；CSV 矩阵格式与原版一致。
    """
    warnings.filterwarnings("ignore", category=RuntimeWarning)

    # 可调参数（按需要微调）
    ALPHA = 0.05          # 显著性阈值
    SLOPE_MIN = 0.005     # 实际意义阈值（每年 <0.5% 视为稳定）
    R2_FLUC = 0.40        # 低于此 R² 值倾向认为波动
    STD_DIFF_MAX = 0.10   # 一阶差分的标准差阈值
    AMP_MAX = 0.30        # 振幅阈值（max(y)-min(y)）

    project_data = {}  # {name: {'percentages': [], 'trend': .., 'model': .., 'r2': .., 'pvalue': ..}}

    for project_name in os.listdir(base_dir):
        project_path = os.path.join(base_dir, project_name)
        if not os.path.isdir(project_path):
            continue

        data = collect_past_10_years_percentages(project_path)
        filtered = [d for d in data if d['percentage'] > 0]
        if len(filtered) < 3:
            continue

        years = np.array([d['year'] for d in filtered], dtype=float)
        y = np.array([d['percentage'] for d in filtered], dtype=float)
        n = len(y)

        # 线性（主模型，使用真实年份刻度）
        X_lin = sm.add_constant(years)
        lin_res = sm.OLS(y, X_lin).fit()
        slope = float(lin_res.params[1])
        p_lin = float(lin_res.pvalues[1])
        r2_lin = float(lin_res.rsquared)

        # 波动度量
        diffs = np.diff(y)
        std_diff = float(np.std(diffs)) if len(diffs) > 0 else 0.0
        amplitude = float(np.max(y) - np.min(y)) if n > 0 else 0.0

        chosen_name = "Linear"
        chosen_formula = f"y = {slope:.4f}*year + {float(lin_res.params[0]):.4f}"
        chosen_r2 = r2_lin
        chosen_p = p_lin
        trend = None

        # 1) 极小斜率 → 稳定（实际意义上）
        if abs(slope) < SLOPE_MIN:
            trend = "Stable"

        # 2) 线性显著 → Increasing / Decreasing
        if trend is None and p_lin < ALPHA:
            trend = "Increasing" if slope > 0 else "Decreasing"

        # 3) 线性不显著：检查波动
        if trend is None and p_lin >= ALPHA:
            # 若明显波动，先标记为 Fluctuating，除非替代模型显著
            prelim_fluc = (r2_lin < R2_FLUC) or (std_diff > STD_DIFF_MAX) or (amplitude > AMP_MAX)

            # 尝试替代模型：对数 / 指数 / 幂（按 1..N 的等距索引，更接近 Excel 趋势线做法）
            X_idx = np.arange(1, n + 1, dtype=float)

            # a) Log: y = a*ln(x) + b（x>0）
            tried_models = []
            if np.all(X_idx > 0):
                X_log = sm.add_constant(np.log(X_idx))
                try:
                    log_res = sm.OLS(y, X_log).fit()
                    p_log = float(log_res.pvalues[1])
                    r2_log = float(log_res.rsquared)
                    a_log = float(log_res.params[1]); b_log = float(log_res.params[0])
                    tried_models.append(("Logarithmic", p_log, r2_log, f"y = {a_log:.4f}ln(x) + {b_log:.4f}",
                                         a_log, None))
                except Exception:
                    pass

            # b) Exp: y = a*exp(b*x)  → ln(y) = ln(a) + b*x（y>0）
            if np.all(y > 0):
                X_exp = sm.add_constant(X_idx)
                try:
                    exp_res = sm.OLS(np.log(y), X_exp).fit()
                    p_exp = float(exp_res.pvalues[1])
                    r2_exp = float(exp_res.rsquared)
                    b_exp = float(exp_res.params[1]); ln_a = float(exp_res.params[0])
                    a_exp = float(np.exp(ln_a))
                    tried_models.append(("Exponential", p_exp, r2_exp, f"y = {a_exp:.4f}e^({b_exp:.4f}x)",
                                         b_exp, None))
                except Exception:
                    pass

            # c) Power: y = a*x^b → ln(y) = ln(a) + b*ln(x)（x>0,y>0）
            if np.all(X_idx > 0) and np.all(y > 0):
                X_pow = sm.add_constant(np.log(X_idx))
                try:
                    pow_res = sm.OLS(np.log(y), X_pow).fit()
                    p_pow = float(pow_res.pvalues[1])
                    r2_pow = float(pow_res.rsquared)
                    b_pow = float(pow_res.params[1]); ln_a2 = float(pow_res.params[0])
                    a_pow = float(np.exp(ln_a2))
                    tried_models.append(("Power", p_pow, r2_pow, f"y = {a_pow:.4f}x^{b_pow:.4f}",
                                         b_pow, None))
                except Exception:
                    pass

            # 选择首个显著（p<α）的替代模型（也可选R²最佳的显著模型）
            sig_models = [m for m in tried_models if m[1] < ALPHA]
            if sig_models:
                # 先用 R² 最大的显著模型
                sig_models.sort(key=lambda t: t[2], reverse=True)
                chosen_name, chosen_p, chosen_r2, chosen_formula, slope_like, _ = sig_models[0]
                # slope_like：log/exp/power 中对应的“方向参数”（a_log、b_exp、b_pow）
                if abs(slope_like) < SLOPE_MIN:
                    trend = "Stable"
                else:
                    trend = "Increasing" if slope_like > 0 else "Decreasing"
            else:
                # 没有显著替代模型
                trend = "Fluctuating" if prelim_fluc else "Stable"

            chosen_p = chosen_p if sig_models else p_lin
            chosen_r2 = chosen_r2 if sig_models else r2_lin

        # 4) 若以上仍未定（极少数情况），回退到线性方向
        if trend is None:
            trend = "Increasing" if slope > 0 else "Decreasing"

        # 记录
        project_data[project_name] = {
            'percentages': y.tolist(),
            'trend': trend,
            'model': chosen_name + " | " + chosen_formula,
            'r2': round(float(chosen_r2), 3),
            'pvalue': round(float(chosen_p), 4)
        }

        print(f"[{project_name}] {trend} | {chosen_name} | R²={chosen_r2:.3f} | p={chosen_p:.4f}")

    # ---------------------------
    # 构造与原版一致的 CSV（矩阵）+ 新增 PValue 行
    # ---------------------------
    if not project_data:
        print("[WARN] No valid project data found.")
        return

    # 对齐不同项目的年份长度
    max_len = max(len(p['percentages']) for p in project_data.values())
    rows = []

    # Year1..YearN
    for i in range(max_len):
        row = [f"Year{i+1}"]
        for proj in project_data.keys():
            vals = project_data[proj]['percentages']
            row.append(round(vals[i], 4) if i < len(vals) else "")
        rows.append(row)

    # Summary rows（与原版一致，并新增 PValue）
    trend_row = ["Trend"] + [p['trend'] for p in project_data.values()]
    model_row = ["Model"] + [p['model'] for p in project_data.values()]
    r2_row    = ["R2"]    + [p['r2']    for p in project_data.values()]
    p_row     = ["PValue"]+ [p['pvalue']for p in project_data.values()]
    rows.extend([trend_row, model_row, r2_row, p_row])

    headers = ["Year"] + list(project_data.keys())
    with open(output_csv, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

    print(f"[DONE] CSV saved in matrix form → {output_csv}")

    # 可选：趋势分布图（若不需要可删除）
    if project_data:
        trends = [p['trend'] for p in project_data.values()]
        counter = Counter(trends)
        types = ["Increasing", "Decreasing", "Stable", "Fluctuating"]
        counts = [counter.get(t, 0) for t in types]

        plt.figure(figsize=(8, 5))
        bars = plt.bar(types, counts, color=['#4CAF50', '#F44336', '#2196F3', '#FFC107'])
        plt.title("Distribution of Mock Usage Trends")
        plt.xlabel("Trend Type")
        plt.ylabel("Number of Projects")
        plt.grid(axis='y', linestyle='--', alpha=0.3)
        for bar in bars:
            h = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, h + 0.2, str(int(h)), ha='center', va='bottom')

        out_img = os.path.splitext(output_csv)[0] + "_trend_distribution.png"
        plt.tight_layout()
        plt.savefig(out_img, dpi=150)
        plt.show()
        print(f"[DONE] Trend distribution plot saved → {out_img}")


# 示例
if __name__ == "__main__":
    analyze_mock_trend(r'RQ 2\\output\\mock_object_by_year', 'mock_trend_analysis_stat.csv')
