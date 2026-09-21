"""
参照 Mock_Pattern_TSE.pdf 里 RQ3 的四张图（Fig.7a/7b/8a/8b），用修正后的
cctr_level_transform_result.csv 重新画一遍，存到 RQ 3/figures/。

数据颗粒度说明：论文的 Fig.7a/7b 是按"每个受影响的测试用例"统计的；我们这里的
cctr_level_transform_result.csv 是按"每个 mock 转换"统计的（一条记录对应一个 mock
object，可能影响多个测试用例）。用 PctChange（该 mock 转换前后的 CCTR 相对变化）
作为影响力指标来复刻同样的"项目内按影响力排名 -> 百分位曲线"画法，口径上是对论文
方法论的近似，不是逐测试用例的精确复刻。

四张图：
  fig7a_upgrade_per_mock_impact.png    Upgrade：CCTR 降幅 vs 排名百分位（对应 Fig.7a）
  fig7b_downgrade_per_mock_impact.png  Downgrade：CCTR 增幅 vs 排名百分位（对应 Fig.7b）
  fig8a_upgrade_project_histogram.png  Upgrade：项目级整体降幅分布（对应 Fig.8a）
  fig8b_downgrade_project_histogram.png Downgrade：项目级整体增幅分布（对应 Fig.8b）
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "figures")
os.makedirs(OUT_DIR, exist_ok=True)

BLUE = "#2a78d6"
GRAY_GRID = "#d8d7d2"
TEXT = "#3a3a38"

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "#8a8a86",
    "axes.labelcolor": TEXT,
    "text.color": TEXT,
    "xtick.color": TEXT,
    "ytick.color": TEXT,
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def load_data():
    return pd.read_csv(os.path.join(SCRIPT_DIR, "cctr_level_transform_result.csv"))


# ---------------------------------------------------------------------------
def per_mock_impact_curve(df, direction, sign):
    """
    对应论文 Fig.7a/7b：项目内按 |PctChange| 降序排名，x = 排名百分位(0-100%)，
    y = sign * PctChange * 100（sign=-1 把 Upgrade 的负数变成正的"降幅%"，
    Downgrade 本来就是正数，sign=1）。
    """
    sub = df[df["Direction"] == direction].copy()
    sub["abspct"] = sub["PctChange"].abs()

    xs, ys = [], []
    for _, g in sub.groupby("Project"):
        g = g.sort_values("abspct", ascending=False).reset_index(drop=True)
        n = len(g)
        if n == 0:
            continue
        pct_rank = (np.arange(1, n + 1) / n) * 100
        xs.append(pct_rank)
        ys.append(sign * g["PctChange"].values * 100)
    return np.concatenate(xs), np.concatenate(ys)


def plot_fig7(df, direction, sign, ylabel, title, out_name, y_max=None):
    x, y = per_mock_impact_curve(df, direction, sign)

    fig, ax = plt.subplots(figsize=(6.4, 4.6), dpi=150)
    ax.scatter(x, y, s=10, color=BLUE, alpha=0.35, edgecolors="none")

    # 40% 阈值处的取值范围（呼应论文里 "40%, X%" 的标注方式）
    near40 = y[(x >= 39) & (x <= 41)]
    if len(near40) > 0:
        lo, hi = np.percentile(near40, [10, 90])
        ax.axvline(40, color="#8a8a86", linewidth=1, linestyle="--")
        ax.annotate(
            f"40%, {lo:.0f}-{hi:.0f}%",
            xy=(40, hi),
            xytext=(46, hi + (y.max() * 0.04 if y.max() > 0 else 4)),
            fontsize=9,
            color=TEXT,
            arrowprops=dict(arrowstyle="-", color="#8a8a86", linewidth=1),
        )

    ax.set_xlabel("Percentage of Converted (ranked by CCTR impact per mock)")
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=12)
    ax.set_xlim(0, 100)
    if y_max:
        ax.set_ylim(0, y_max)
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=100))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=100))
    ax.grid(True, color=GRAY_GRID, linewidth=0.6)
    ax.set_axisbelow(True)

    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, out_name))
    plt.close(fig)


# ---------------------------------------------------------------------------
def project_level_ratio(df, direction):
    sub = df[df["Direction"] == direction]
    g = sub.groupby("Project").apply(
        lambda x: x["CCTRChange"].sum() / x["BeforeCCTR"].sum() if x["BeforeCCTR"].sum() else np.nan,
        include_groups=False,
    )
    return g.dropna()


def plot_fig8(ratios, sign, bins_pct, title, out_name):
    """对应论文 Fig.8a/8b：project 级整体 CCTR 变化比例分布直方图。"""
    values = (sign * ratios * 100).values
    bins = bins_pct + [np.inf]
    labels = []
    for i in range(len(bins_pct)):
        lo, hi = bins_pct[i], bins_pct[i + 1] if i + 1 < len(bins_pct) else None
        if hi is None:
            labels.append(f">{lo}%")
        else:
            labels.append(f"[{lo}%, {hi}%)" if i > 0 else f"[{lo}%, {hi}%)")
    # 用 pandas.cut 精确切分
    edges = bins_pct + [np.inf]
    cats = pd.cut(values, bins=edges, right=False)
    counts = pd.Series(cats).value_counts().sort_index()

    tick_labels = []
    for i in range(len(bins_pct)):
        lo = bins_pct[i]
        hi = bins_pct[i + 1] if i + 1 < len(bins_pct) else None
        tick_labels.append(f"[{lo}%,{hi}%)" if hi is not None else f">{lo}%")

    fig, ax = plt.subplots(figsize=(6.4, 4.6), dpi=150)
    x_pos = np.arange(len(counts))
    bars = ax.bar(x_pos, counts.values, width=0.62, color=BLUE)

    for rect, v in zip(bars, counts.values):
        if v > 0:
            ax.annotate(str(int(v)), xy=(rect.get_x() + rect.get_width() / 2, v),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=10, color=TEXT)

    ax.set_xticks(x_pos)
    ax.set_xticklabels(tick_labels, fontsize=9)
    ax.set_xlabel("CCTR Change Ratio (project-level)")
    ax.set_ylabel("Number of Projects")
    ax.set_title(title, fontsize=12)
    ax.grid(True, axis="y", color=GRAY_GRID, linewidth=0.6)
    ax.set_axisbelow(True)

    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, out_name))
    plt.close(fig)


# ---------------------------------------------------------------------------
def main():
    df = load_data()

    # Fig.7a: Upgrading L0 mocks (L0->L1/L2) — CCTR Reduction Ratio per mock
    plot_fig7(
        df, "Upgrade", sign=-1,
        ylabel="CCTR Reduction Ratio per mock (%)",
        title="(a) Upgrading L0 mocks (L0→L1/L2)",
        out_name="fig7a_upgrade_per_mock_impact.png",
        y_max=100,
    )

    # Fig.7b: Downgrading shared mocks (L1/L2->L0) — CCTR Increase Ratio per mock
    # y 轴封顶在 300%（呼应论文原图的轴范围），极端离群值会被裁掉，避免把曲线主体压扁
    plot_fig7(
        df, "Downgrade", sign=1,
        ylabel="CCTR Increase Ratio per mock (%)",
        title="(b) Downgrading shared mocks (L1/L2→L0)",
        out_name="fig7b_downgrade_per_mock_impact.png",
        y_max=300,
    )

    # Fig.8a: Upgrading all L0 mocks (project-level aggregate reduction)
    up_ratios = project_level_ratio(df, "Upgrade")
    plot_fig8(
        up_ratios, sign=-1,
        bins_pct=[0, 20, 40, 60, 80, 100],
        title="(a) Upgrading all L0 mocks",
        out_name="fig8a_upgrade_project_histogram.png",
    )

    # Fig.8b: Downgrading all shared mocks (project-level aggregate increase)
    down_ratios = project_level_ratio(df, "Downgrade")
    plot_fig8(
        down_ratios, sign=1,
        bins_pct=[0, 20, 40, 60, 80, 100],
        title="(b) Downgrading all shared mocks",
        out_name="fig8b_downgrade_project_histogram.png",
    )

    print(f"Saved 4 figures to {OUT_DIR}")


if __name__ == "__main__":
    main()
