import pandas as pd
from scipy.stats import kruskal, mannwhitneyu
import itertools
import numpy as np

# === Step 1: 读取数据 ===
df = pd.read_csv("result.csv")

# 检查列名
required_cols = ["mockPatternLevel", "avg_added_cctr_per_test_case"]
for col in required_cols:
    if col not in df.columns:
        raise ValueError(f"缺少必要列: {col}")

# === Step 2: 按 level 分组数据 ===
groups = {
    level: df[df["mockPatternLevel"] == level]["avg_added_cctr_per_test_case"].dropna()
    for level in sorted(df["mockPatternLevel"].unique())
}

# === Step 3: Kruskal–Wallis 总体显著性检验 ===
kw_stat, kw_p = kruskal(*groups.values())
print("="*70)
print("Kruskal–Wallis test for CCTR differences among mock levels")
print(f"H statistic = {kw_stat:.3f}, p-value = {kw_p:.3e} ({kw_p:.2%})")

# === Step 4: 两两比较（Mann–Whitney U + Cliff’s Delta）===
def cliffs_delta(x, y):
    """计算 Cliff's Delta 效应量"""
    m, n = len(x), len(y)
    total = 0
    for xi in x:
        total += np.sum(xi > y) - np.sum(xi < y)
    delta = total / (m * n)
    return delta

print("\nPairwise comparisons (Mann–Whitney U tests):")
for (i, j) in itertools.combinations(groups.keys(), 2):
    g1, g2 = groups[i], groups[j]
    u_stat, p_value = mannwhitneyu(g1, g2, alternative='two-sided')
    delta = cliffs_delta(g1.to_numpy(), g2.to_numpy())
    effect = (
        "negligible" if abs(delta) < 0.147 else
        "small" if abs(delta) < 0.33 else
        "medium" if abs(delta) < 0.474 else
        "large"
    )
    print(f"  Level {i} vs Level {j}: U={u_stat:.2f}, p={p_value:.3e} ({p_value:.2%}), "
        f"Cliff’s delta={delta:.3f} ({effect} effect)")

# === Step 5: 解释提示 ===
print("\nInterpretation guide:")
print(" - p < 0.05 → 差异显著")
print(" - Cliff’s delta 绝对值越大表示效应越强：")
print("   negligible < 0.147 < small < 0.33 < medium < 0.474 < large")
print("="*70)
