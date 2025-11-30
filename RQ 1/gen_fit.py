import os
import pandas as pd
import matplotlib.pyplot as plt

# =============================
# 读取 CSV
# =============================
df = pd.read_csv("mock_object_summary.csv")

# 基本清洗
df["MockLevel"] = pd.to_numeric(df["MockLevel"], errors="coerce").fillna(0).astype(int)
df["TestCount"] = pd.to_numeric(df["TestCount"], errors="coerce").fillna(0)
df["StubCount"] = pd.to_numeric(df["StubCount"], errors="coerce").fillna(0)

# 只保留 Level 0/1/2
df = df[df["MockLevel"].isin([0, 1, 2])].copy()

# 组合 Project + Dependency 作为依赖键，避免同名冲突
df["ProjectDependency"] = df["Project"].astype(str) + "::" + df["Dependency"].astype(str)

# =============================
# 计算「每个 dependency 下的 mock 数量」和「每个 dependency 下的总 TestCount」
# =============================
dep_mock_counts = (
    df.groupby("ProjectDependency")
      .size()
      .rename("MocksPerDependency")
      .reset_index()
)

dep_test_counts = (
    df.groupby("ProjectDependency")["TestCount"]
      .sum()
      .rename("TestsPerDependency")
      .reset_index()
)

# 合回到每个 mock 行上
df = df.merge(dep_mock_counts, on="ProjectDependency", how="left")
df = df.merge(dep_test_counts, on="ProjectDependency", how="left")


# =============================
# 自动等宽区间分桶函数：给定宽度 & 最大值
# =============================
def add_bucket_column(df, source_col, bucket_col, bin_width, max_value):
    """
    根据给定区间宽度 bin_width 和最大值 max_value 等宽分桶。
    [0, bin_width), [bin_width, 2*bin_width), ..., [max_value, +inf)
    最后一个桶的标签例如 "80+"。
    """
    # 如果这一列全是 NaN 或 <=0，就统一给一个 0 桶
    col_max = df[source_col].max()
    if pd.isna(col_max) or col_max < 0:
        df[bucket_col] = "0"
        return df

    # 构造边界：0, bin_width, 2*bin_width, ..., max_value, inf
    # 注意：range 到 max_value（不含），最后手动加 max_value 和 inf
    edges = list(range(0, max_value, bin_width))
    if edges[-1] != max_value:
        edges.append(max_value)
    edges.append(float("inf"))

    # 生成标签：例如 0–9, 10–19, ..., 70–79, 80+
    labels = []
    for i in range(len(edges) - 2):
        start = int(edges[i])
        end = int(edges[i + 1] - 1)
        labels.append(f"{start}–{end}")
    labels.append(f"{int(max_value)}+")

    df[bucket_col] = pd.cut(
        df[source_col],
        bins=edges,
        labels=labels,
        include_lowest=True,
        right=False,  # 左闭右开 [start, end)
    )
    return df


# =============================
# 绘制比例直方图函数（带百分比标签）
# =============================
def plot_level_ratio_by_bucket(
    df,
    bucket_col,
    weight_col,
    title,
    ylabel,
    filename,
    level_order=(0, 1, 2),
):
    """
    df         : DataFrame（以 mock 为粒度）
    bucket_col : 分桶后的列名
    weight_col : 权重列名；'mock_count' 表示每行权重为 1
    """

    # 计算每个桶、每个 Level 的权重和
    if weight_col == "mock_count":
        tmp = (
            df.groupby([bucket_col, "MockLevel"])
              .size()
              .reset_index(name="value")
        )
    else:
        tmp = (
            df.groupby([bucket_col, "MockLevel"])[weight_col]
              .sum()
              .reset_index(name="value")
        )

    # 透视表：index = bucket 区间, columns = MockLevel, values = value
    pivot = tmp.pivot(index=bucket_col, columns="MockLevel", values="value").fillna(0)

    # 转成字符串列名并保证顺序
    pivot.columns = pivot.columns.astype(str)
    str_level_order = [str(lv) for lv in level_order]
    for lv in str_level_order:
        if lv not in pivot.columns:
            pivot[lv] = 0
    pivot = pivot[str_level_order]

    # 计算百分比
    row_sums = pivot.sum(axis=1)
    ratio = pivot.div(row_sums.replace(0, 1), axis=0) * 100

    # 绘图
    fig, ax = plt.subplots(figsize=(8, 5))
    ratio.plot(kind="bar", width=0.8, ax=ax)

    plt.title(title)
    plt.xlabel(bucket_col)
    plt.ylabel(ylabel + " (%)")
    plt.legend(title="MockLevel", labels=["Level 0", "Level 1", "Level 2"])
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    # 在柱子顶部显示百分比
    for container in ax.containers:
        ax.bar_label(
            container,
            fmt="%.1f%%",
            label_type="edge",
            fontsize=8,
            padding=2,
        )
    ax.set_ylim(0, 110)

    os.makedirs("figures", exist_ok=True)
    plt.savefig(os.path.join("figures", filename), dpi=300)
    plt.close()


# =============================
# 1️⃣ 维度一：每个 dependency 下的 mock 数量
# =============================
# 这里举例：区间宽度 10，最大值 80；>80 的都归到 "80+"
df = add_bucket_column(
    df,
    source_col="MocksPerDependency",
    bucket_col="MocksPerDepBucket",
    bin_width=5,
    max_value=40,
)

# 图 1-A：权重 = mock 数
plot_level_ratio_by_bucket(
    df=df,
    bucket_col="MocksPerDepBucket",
    weight_col="mock_count",
    title="Distribution of Mock Levels by MocksPerDependency",
    ylabel="Proportion of Mocks",
    filename="hist_mocks_per_dep_mock_ratio.png",
)

# 图 1-B：权重 = TestCount（受影响的测试数量）
plot_level_ratio_by_bucket(
    df=df,
    bucket_col="MocksPerDepBucket",
    weight_col="TestCount",
    title="Distribution of Affected Test Cases by MocksPerDependency",
    ylabel="Proportion of Test Cases",
    filename="hist_mocks_per_dep_testcase_ratio.png",
)


# =============================
# 2️⃣ 维度二：每个 dependency 下受影响的测试数量
# =============================
# 举例：区间宽度 50，最大值 400；>400 的归到 "400+"
df = add_bucket_column(
    df,
    source_col="TestsPerDependency",
    bucket_col="TestsPerDepBucket",
    bin_width=5,
    max_value=40,
)

# 图 2-A：权重 = mock 数
plot_level_ratio_by_bucket(
    df=df,
    bucket_col="TestsPerDepBucket",
    weight_col="mock_count",
    title="Distribution of Mock Levels by TestsPerDependency",
    ylabel="Proportion of Mocks",
    filename="hist_tests_per_dep_mock_ratio.png",
)

# 图 2-B：权重 = TestCount
plot_level_ratio_by_bucket(
    df=df,
    bucket_col="TestsPerDepBucket",
    weight_col="TestCount",
    title="Distribution of Affected Test Cases by TestsPerDependency",
    ylabel="Proportion of Test Cases",
    filename="hist_tests_per_dep_testcase_ratio.png",
)


# =============================
# 3️⃣ 维度三：每个 mock 的 StubCount
# =============================
# StubCount 通常比较小，这里用宽度 1，最大值 8；>8 归到 "8+"
df = add_bucket_column(
    df,
    source_col="StubCount",
    bucket_col="StubCountBucket",
    bin_width=1,
    max_value=8,
)

# 图 3-A：权重 = mock 数
plot_level_ratio_by_bucket(
    df=df,
    bucket_col="StubCountBucket",
    weight_col="mock_count",
    title="Distribution of Mock Levels by StubCount (per Mock)",
    ylabel="Proportion of Mocks",
    filename="hist_stubcount_mock_ratio.png",
)

# 图 3-B：权重 = TestCount
plot_level_ratio_by_bucket(
    df=df,
    bucket_col="StubCountBucket",
    weight_col="TestCount",
    title="Distribution of Affected Test Cases by StubCount (per Mock)",
    ylabel="Proportion of Test Cases",
    filename="hist_stubcount_testcase_ratio.png",
)

print("✅ 已生成 6 张图，保存在 ./figures 目录下。")
