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

# 合回到每个 mock 行上（这样每个 mock 都知道自己所在依赖有多少 mock / 多少 test）
df = df.merge(dep_mock_counts, on="ProjectDependency", how="left")
df = df.merge(dep_test_counts, on="ProjectDependency", how="left")


# =============================
# 工具函数：把数值离散化成桶（0,1,2,...,max_bin+）
# =============================
def add_bucket_column(df, source_col, bucket_col, max_bin=8):
    def bucket_func(v):
        try:
            v = int(round(v))
        except Exception:
            v = 0
        if v >= max_bin:
            return f"{max_bin}+"
        else:
            return str(v)

    df[bucket_col] = df[source_col].apply(bucket_func)
    return df


# =============================
# 工具函数：画「Level 比例」柱状图，显示百分比
# =============================
def plot_level_ratio_by_bucket(
    df,
    bucket_col,
    weight_col,
    title,
    ylabel,
    filename,
    level_order=(0, 1, 2),
    max_bin=8,
):
    """
    df         : DataFrame（以 mock 为粒度）
    bucket_col : 分桶后的列名（字符串）
    weight_col : 权重列名；如果是 'mock_count' 表示每行权重为 1
    title      : 图标题
    ylabel     : y 轴标签前缀（会自动加 "(%)"）
    filename   : 输出文件名
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

    # 透视表：index = bucket, columns = MockLevel, values = value
    pivot = tmp.pivot(index=bucket_col, columns="MockLevel", values="value").fillna(0)

    # 将列名统一转成字符串，方便按 '0','1','2' 排序
    pivot.columns = pivot.columns.astype(str)
    str_level_order = [str(lv) for lv in level_order]

    # 确保 Level 列顺序存在
    for lv in str_level_order:
        if lv not in pivot.columns:
            pivot[lv] = 0
    pivot = pivot[str_level_order]

    # 计算比例，并转为百分比
    row_sums = pivot.sum(axis=1)
    ratio = pivot.div(row_sums.replace(0, 1), axis=0) * 100

    # 桶顺序：'0','1',...,'max_bin-1','max_bin+'
    bucket_order = [str(i) for i in range(max_bin)] + [f"{max_bin}+"]
    ratio = ratio.reindex(bucket_order).dropna(how="all")

    # 绘图
    fig, ax = plt.subplots(figsize=(8, 5))
    ratio.plot(kind="bar", width=0.8, ax=ax)

    plt.title(title)
    plt.xlabel(bucket_col)
    plt.ylabel(ylabel + " (%)")
    plt.legend(title="MockLevel", labels=["Level 0", "Level 1", "Level 2"])
    plt.tight_layout()

    # 在柱子顶部添加百分比数值标签
    for container in ax.containers:
        ax.bar_label(
            container,
            fmt="%.1f%%",  # 百分比格式
            label_type="edge",
            fontsize=8,
            padding=2,
        )

    # y 轴 0–110%
    ax.set_ylim(0, 110)

    os.makedirs("figures", exist_ok=True)
    plt.savefig(os.path.join("figures", filename), dpi=300)
    plt.close()


# =============================
# 1️⃣ 维度一：每个 dependency 下的 mock 数量（MocksPerDependency）
# =============================

df = add_bucket_column(df, source_col="MocksPerDependency", bucket_col="MocksPerDepBucket", max_bin=8)

# 图 1-A：横轴 = 每个 dependency 的 mock 数量；权重 = mock 数（每个 mock 算 1）
plot_level_ratio_by_bucket(
    df=df,
    bucket_col="MocksPerDepBucket",
    weight_col="mock_count",
    title="Distribution of Mock Levels by MocksPerDependency",
    ylabel="Proportion of Mocks",
    filename="hist_mocks_per_dep_mock_ratio.png",
    max_bin=8,
)

# 图 1-B：横轴 = 每个 dependency 的 mock 数量；权重 = TestCount（受影响的 test 数）
plot_level_ratio_by_bucket(
    df=df,
    bucket_col="MocksPerDepBucket",
    weight_col="TestCount",
    title="Distribution of Affected Test Cases by MocksPerDependency",
    ylabel="Proportion of Test Cases",
    filename="hist_mocks_per_dep_testcase_ratio.png",
    max_bin=8,
)


# =============================
# 2️⃣ 维度二：每个 dependency 下受影响的测试用例总数（TestsPerDependency）
# =============================

df = add_bucket_column(df, source_col="TestsPerDependency", bucket_col="TestsPerDepBucket", max_bin=8)

# 图 2-A：横轴 = 每个 dependency 的总 TestCount；权重 = mock 数
plot_level_ratio_by_bucket(
    df=df,
    bucket_col="TestsPerDepBucket",
    weight_col="mock_count",
    title="Distribution of Mock Levels by TestsPerDependency",
    ylabel="Proportion of Mocks",
    filename="hist_tests_per_dep_mock_ratio.png",
    max_bin=8,
)

# 图 2-B：横轴 = 每个 dependency 的总 TestCount；权重 = TestCount
plot_level_ratio_by_bucket(
    df=df,
    bucket_col="TestsPerDepBucket",
    weight_col="TestCount",
    title="Distribution of Affected Test Cases by TestsPerDependency",
    ylabel="Proportion of Test Cases",
    filename="hist_tests_per_dep_testcase_ratio.png",
    max_bin=8,
)


# =============================
# 3️⃣ 维度三：每个 mock 自己的 StubCount
# =============================

df = add_bucket_column(df, source_col="StubCount", bucket_col="StubCountBucket", max_bin=8)

# 图 3-A：横轴 = 每个 mock 的 StubCount；权重 = mock 数
plot_level_ratio_by_bucket(
    df=df,
    bucket_col="StubCountBucket",
    weight_col="mock_count",
    title="Distribution of Mock Levels by StubCount (per Mock)",
    ylabel="Proportion of Mocks",
    filename="hist_stubcount_mock_ratio.png",
    max_bin=8,
)

# 图 3-B：横轴 = 每个 mock 的 StubCount；权重 = TestCount
plot_level_ratio_by_bucket(
    df=df,
    bucket_col="StubCountBucket",
    weight_col="TestCount",
    title="Distribution of Affected Test Cases by StubCount (per Mock)",
    ylabel="Proportion of Test Cases",
    filename="hist_stubcount_testcase_ratio.png",
    max_bin=8,
)

print("✅ 已生成 6 张图，已保存到 ./figures 目录下。")
