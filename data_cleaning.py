import pandas as pd
import re

def unify_amount(text):
    if pd.isna(text) or not str(text).strip():
        return None
    text = str(text).replace(",", "").replace("，", "").replace("¥", "").replace("￥", "").replace(" ", "")
    match = re.search(r"(\d+\.?\d*)", text)
    if not match:
        return None
    value = float(match.group(1))
    if "万" in text:
        value *= 10000
    return round(value, 2)

df = pd.read_excel("原始数据.xlsx")
df["中标金额_元"] = df["中标金额"].apply(unify_amount)
df = df.drop_duplicates(subset=["链接", "中标供应商名称"], keep="first")
df.loc[df["中标金额_元"] > 50000000, "中标金额_元"] = None
df.to_excel("清洗后_中标数据.xlsx", index=False)
print("清洗完成，剩余记录数：", len(df))
