import pandas as pd
import matplotlib.pyplot as plt


def parse_reduction_ratio_to_num(s: pd.Series) -> pd.Series:
    rr = (
        s.astype(str)
         .str.strip()
         .str.replace("%", "", regex=False)
    )
    return pd.to_numeric(rr, errors="coerce") / 100.0


def add_project_ecdf_columns(
    df: pd.DataFrame,
    y_col: str = "ReductionRatio_num",
    sort_ascending: bool = True,
    x_col_out: str = "ecdf_x",
    y_col_out: str = "ecdf_y",
) -> pd.DataFrame:
    """
    对每个 Project 单独计算 ECDF：
      - 先按 y_col 排序（升序=标准ECDF）
      - ecdf_x = i/n (i从1开始)
      - ecdf_y = 排序后的 y_col
    最终把 ecdf_x / ecdf_y 写回每一行（行仍保留，只是新增列）。
    """
    df = df.copy()
    df["_row_id"] = range(len(df))

    pieces = []
    for project, g in df.groupby("Project", sort=False):
        g = g.copy()
        # 只对可用数据算 ECDF（NaN 不参与）
        valid = g[g[y_col].notna()].copy()
        invalid = g[g[y_col].isna()].copy()

        if len(valid) > 0:
            valid = valid.sort_values(y_col, ascending=sort_ascending, kind="mergesort").reset_index(drop=True)
            n = len(valid)
            valid[x_col_out] = (pd.Series(range(1, n + 1)) / n).astype(float)
            valid[y_col_out] = valid[y_col].astype(float)

        # NaN 的行，ecdf_x/ecdf_y 也给 NaN（保留行）
        if len(invalid) > 0:
            invalid[x_col_out] = pd.NA
            invalid[y_col_out] = pd.NA

        pieces.append(pd.concat([valid, invalid], ignore_index=True))

    out = pd.concat(pieces, ignore_index=True)
    # 按原始顺序恢复
    out = out.sort_values("_row_id").drop(columns=["_row_id"]).reset_index(drop=True)
    return out


def plot_from_ecdf_csv(df: pd.DataFrame, title: str, out_png: str, y_min=None, y_max=None):
    plt.figure()

    for project, g in df.groupby("Project", sort=True):
        gg = g.dropna(subset=["ecdf_x", "ecdf_y"]).copy()
        if gg.empty:
            continue

        # ✅ 关键：按 ecdf_x 排序，保证连线单调不折返
        gg = gg.sort_values("ecdf_x", ascending=True, kind="mergesort")

        plt.plot(gg["ecdf_x"].to_numpy(), gg["ecdf_y"].to_numpy(), alpha=0.6, linewidth=1.0)

    plt.title(title)
    plt.xlabel("ECDF x (i / n) within each project")
    plt.ylabel("ReductionRatio (numeric)")
    if (y_min is not None) or (y_max is not None):
        plt.ylim(bottom=y_min, top=y_max)

    plt.grid(True, linewidth=0.5, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_png, dpi=300)
    plt.close()



def main(input_csv: str):
    df = pd.read_csv(input_csv)

    # 解析比例
    df["ReductionRatio_num"] = parse_reduction_ratio_to_num(df["ReductionRatio"])

    # 分组
    shared = df[df["FromLevel"] != 0].copy()
    non_shared = df[df["FromLevel"] == 0].copy()

    # ✅ shared：只排除 ReductionRatio_num == 0（按你最新要求）
    shared = shared[
        shared["ReductionRatio_num"].notna() &
        (shared["ReductionRatio_num"] != 0)
    ].copy()

    # （可选）如果你仍然想让 shared 只看正值：打开这一段
    # shared = shared[shared["ReductionRatio_num"] > 0].copy()

    # non_shared：不额外过滤（保留0/负值/正值，只要不是NaN）
    # 如果你想排除 NaN，也可以加：non_shared = non_shared[non_shared["ReductionRatio_num"].notna()].copy()

    # 计算并写入 ECDF 列（⚠️ 这里会真正写到 CSV）
    # ECDF 的标准做法：按 y 升序（单调上升）
    shared_out = add_project_ecdf_columns(shared, sort_ascending=True)
    non_shared_out = add_project_ecdf_columns(non_shared, sort_ascending=True)

    # 输出 CSV（带 ecdf_x/ecdf_y）
    shared_out.to_csv("shared_ecdf.csv", index=False)
    non_shared_out.to_csv("non_shared_ecdf.csv", index=False)

    # 可选：直接用这些 CSV 列画图
    plot_from_ecdf_csv(
        shared_out,
        title="ECDF of ReductionRatio (shared, FromLevel != 0)",
        out_png="ecdf_shared.png",
        y_min=0.0,
        y_max=3.0
    )
    plot_from_ecdf_csv(
        non_shared_out,
        title="ECDF of ReductionRatio (non-shared, FromLevel == 0)",
        out_png="ecdf_non_shared.png",
        y_min=None,
        y_max=None
    )



if __name__ == "__main__":
    main("CCTR_Conversion_Summary.csv")  # 改成你的文件名