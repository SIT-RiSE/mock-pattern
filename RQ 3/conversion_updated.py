import pandas as pd

# 读取两个 CSV 文件
df_level0 = pd.read_csv("L0_conversion_result.csv")
df_result = pd.read_csv("result.csv")

# -----------------------------
# 1️⃣ Level 0 → Level 1 / 2
# -----------------------------
df_a = pd.DataFrame()
df_a["Project"] = df_level0["Project"]
df_a["ConvertedFrom"] = 0
df_a["ConvertedTo"] = df_level0["ConvertedLevel"]
df_a["BeforeCount"] = df_level0["L0Count"]
df_a["AfterCount"] = 1
df_a["AvgBeforeCount"] = df_level0["L0Count"]
df_a["AvgAfterCount"] = 1
df_a["CCTRChange"] = -1 * df_level0["CCTRReduction"]
df_a["CCTRChangePerTest"] = -1 * df_level0["CCTRReductionPerTest"]
df_a['RawCCTR'] = df_level0['RawCCTR']
df_a["%"] = df_a["CCTRChange"] / df_level0["RawCCTR"]

# -----------------------------
# 2️⃣ Level 1 / 2 → Level 0
# -----------------------------
df_b = df_result[df_result["MockLevel"].isin([1, 2])].copy()

df_b["Project"] = df_b["Project"]
df_b["ConvertedFrom"] = df_b["MockLevel"]
df_b["ConvertedTo"] = 0
df_b["BeforeCount"] = 1
df_b["AfterCount"] = df_b["TestCount"]
df_b["AvgBeforeCount"] = 1
df_b["AvgAfterCount"] = df_b["TestCount"]
df_b["CCTRChange"] = (df_b["Level0CCTR"] - df_b["AvgAddedCCTR"]) * df_b["TestCount"]
df_b["CCTRChangePerTest"] = df_b["Level0CCTR"] - df_b["AvgAddedCCTR"]
df_b['RawCCTR'] = df_result['RawCCTR']
df_b["%"] = df_b["CCTRChange"] / df_result["RawCCTR"]
# -----------------------------
# 只保留统一的列结构
# -----------------------------
cols = [
    "Project",
    "ConvertedFrom",
    "ConvertedTo",
    "BeforeCount",
    "AfterCount",
    "CCTRChange",
    "CCTRChangePerTest",
    "RawCCTR",
    "%"
]

df_a = df_a[cols]
df_b = df_b[cols]

# -----------------------------
# 合并两类结果
# -----------------------------
conversion_summary = pd.concat([df_a, df_b], ignore_index=True)

# 保存到 CSV
conversion_summary.to_csv("CCTR_Conversion_Summary.csv", index=False)

print(conversion_summary.head())

# 按转换类型分组聚合
group_summary = conversion_summary.groupby(["ConvertedFrom", "ConvertedTo"]).agg(
    ConversionCount=("Project", "count"),
    TotalBeforeMocks=("BeforeCount", "sum"),
    TotalAfterMocks=("AfterCount", "sum"),
    AvgBeforeCount=("BeforeCount", "mean"),
    AvgAfterCount=("AfterCount", "mean"),
    AvgCCTRChange=("CCTRChange", "mean"),
    AvgCCTRChangePerTest=("CCTRChangePerTest", "mean"),    
    Prestangeimpact=("%", "mean")
    
)
# 输出或保存
print(group_summary)
group_summary.to_csv("CCTR_Conversion_Group_Summary.csv", index=False)
