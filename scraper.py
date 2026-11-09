"""
China Government Procurement Website Scraper
Target: Winning bid announcements related to power devices / semiconductors
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import quote
import pandas as pd
import time
import random
import re
import csv
import os
from datetime import datetime

# ==================== Config ====================
KEYWORDS = [
    "功率器件", "半导体", "集成电路", "IGBT", "微控制器",
    "传感器", "功率模块", "MOSFET", "整流桥", "晶闸管",
    "功率半导体", "碳化硅", "SiC", "氮化镓", "GaN",
    "电力电子", "变频器", "逆变器", "驱动芯片", "电源模块"
]

EXCLUDE_WORDS = [
    "服务平台", "支撑服务", "体系建设", "课题研究",
    "信息化", "软件开发", "运维服务", "咨询服务",
    "培训", "监理", "检测服务", "评估服务", "课题"
]

MAX_PAGES_PER_KEYWORD = 3
DELAY_RANGE = (2.8, 5.2)
CSV_FILE = f"政府采购网_中标结果_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
ERROR_LOG = "error_log.txt"
# ================================================


def create_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"}
    )
    return driver


def random_delay():
    time.sleep(random.uniform(*DELAY_RANGE))


def extract_raw_amount(text):
    if not text:
        return ""
    text = str(text).strip()
    text = re.sub(r"\s+", "", text)
    return text


def should_exclude(title):
    title = title.lower()
    return any(word in title for word in EXCLUDE_WORDS)


def is_result_announcement(title):
    title_lower = title.lower()
    if any(k in title_lower for k in ["候选人", "中标候选人"]):
        return False
    if any(k in title_lower for k in ["成交", "中标结果", "结果公告", "中标（成交）"]):
        return True
    if title.endswith("中标公告") and "结果" not in title:
        return False
    return True


def extract_list_page(driver):
    items = []
    try:
        WebDriverWait(driver, 12).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ul.vT-srch-result-list-bid li"))
        )
        elements = driver.find_elements(By.CSS_SELECTOR, "ul.vT-srch-result-list-bid li")

        for elem in elements:
            try:
                a_tag = elem.find_element(By.CSS_SELECTOR, "a")
                title = a_tag.text.strip()
                link = a_tag.get_attribute("href")
                full_text = elem.text

                publish_time = ""
                buyer = ""
                agency = ""

                time_match = re.search(r"(\d{4}\.\d{2}\.\d{2}\s+\d{2}:\d{2}:\d{2})", full_text)
                if time_match:
                    publish_time = time_match.group(1)

                buyer_match = re.search(r"采购人[：:]\s*([^|]+)", full_text)
                if buyer_match:
                    buyer = buyer_match.group(1).strip()

                agency_match = re.search(r"代理机构[：:]\s*([^|\n]+)", full_text)
                if agency_match:
                    agency = agency_match.group(1).strip()

                if title and link:
                    items.append({
                        "标题": title,
                        "链接": link,
                        "发布时间": publish_time,
                        "采购人": buyer,
                        "代理机构": agency
                    })
            except Exception:
                continue
    except Exception as e:
        print(f"  List page extraction error: {e}")
    return items


def extract_from_text(page_text):
    info = {
        "项目编号": "",
        "中标供应商名称": "",
        "中标供应商地址": "",
        "中标金额": "",
        "标的物名称": "",
        "品牌": "",
        "规格型号": "",
        "数量": "",
        "单价": ""
    }

    m = re.search(r"项目编号[：:]\s*([A-Za-z0-9\-（）()]+)", page_text)
    if m:
        info["项目编号"] = m.group(1).strip()

    name_patterns = [
        r"供应商名称[：:]\s*([^\n\r]+)",
        r"中标供应商名称[：:]\s*([^\n\r]+)",
        r"成交供应商[：:]\s*([^\n\r]+)",
        r"供应商[：:]\s*([^\n\r]+)",
    ]
    for p in name_patterns:
        m = re.search(p, page_text)
        if m:
            name = m.group(1).strip()
            if len(name) > 3 and "详见" not in name:
                info["中标供应商名称"] = name
                break

    addr_patterns = [
        r"供应商地址[：:]\s*([^\n\r]+)",
        r"中标供应商地址[：:]\s*([^\n\r]+)",
        r"供应商单位地址[：:]\s*([^\n\r]+)",
    ]
    for p in addr_patterns:
        m = re.search(p, page_text)
        if m:
            info["中标供应商地址"] = m.group(1).strip()
            break

    amount_patterns = [
        r"中标（成交）金额[：:]\s*([^\n\r]+)",
        r"中标\(成交\)金额[：:]\s*([^\n\r]+)",
        r"成交金额[：:]\s*([^\n\r]+)",
        r"中标金额[：:]\s*([^\n\r]+)",
        r"报价[：:]\s*([^\n\r]+)",
        r"总价[：:]\s*([^\n\r]+)",
        r"合价[：:]\s*([^\n\r]+)",
        r"投标报价[：:]\s*([^\n\r]+)",
        r"金额[：:]\s*([¥￥]?\s*[\d,]+\.?\d*\s*[万元]?)",
    ]
    for p in amount_patterns:
        m = re.search(p, page_text)
        if m:
            raw = extract_raw_amount(m.group(1))
            num_match = re.search(r"(\d+\.?\d*)", raw.replace(",", ""))
            if num_match and float(num_match.group(1)) >= 100:
                info["中标金额"] = raw
                break

    for pattern, key in [
        (r"(?:货物名称|名称)[：:]\s*([^\n\r]+)", "标的物名称"),
        (r"品牌[（(]?如有[）)]?[：:]\s*([^\n\r]+)", "品牌"),
        (r"(?:规格型号|型号)[：:]\s*([^\n\r]+)", "规格型号"),
        (r"数量[：:]\s*([^\n\r]+)", "数量"),
        (r"单价[：:]\s*([^\n\r]+)", "单价"),
    ]:
        m = re.search(pattern, page_text)
        if m:
            val = m.group(1).strip()
            if key == "单价":
                val = extract_raw_amount(val)
            info[key] = val

    return info


def extract_detail_page(driver, url, title):
    records = []
    base = {
        "项目名称": title,
        "项目编号": "",
        "中标供应商名称": "",
        "中标供应商地址": "",
        "中标金额": "",
        "标的物名称": "",
        "品牌": "",
        "规格型号": "",
        "数量": "",
        "单价": "",
        "发布时间": "",
        "采购人": "",
        "代理机构": "",
        "链接": url
    }

    try:
        driver.get(url)
        random_delay()
        page_text = driver.find_element(By.TAG_NAME, "body").text

        text_info = extract_from_text(page_text)
        base.update({k: v for k, v in text_info.items() if v})

        try:
            tables = pd.read_html(driver.page_source)
            goods_found = False

            for table in tables:
                col_str = " ".join([str(c) for c in table.columns])
                if any(k in col_str for k in ["货物名称", "名称", "型号", "品牌", "单价", "供应商名称", "金额"]):
                    for _, row in table.iterrows():
                        rec = base.copy()
                        for col in table.columns:
                            col_name = str(col)
                            val = str(row[col]) if pd.notna(row[col]) else ""

                            if "货物名称" in col_name or col_name.strip() == "名称":
                                rec["标的物名称"] = val
                            elif "品牌" in col_name:
                                rec["品牌"] = val
                            elif "型号" in col_name or "规格" in col_name:
                                rec["规格型号"] = val
                            elif "数量" in col_name:
                                rec["数量"] = val
                            elif "单价" in col_name:
                                rec["单价"] = extract_raw_amount(val)
                            elif "供应商名称" in col_name and val and not rec["中标供应商名称"]:
                                rec["中标供应商名称"] = val
                            elif "地址" in col_name and val and not rec["中标供应商地址"]:
                                rec["中标供应商地址"] = val
                            elif ("金额" in col_name or "合价" in col_name or "报价" in col_name) and val:
                                raw = extract_raw_amount(val)
                                num_match = re.search(r"(\d+\.?\d*)", raw.replace(",", ""))
                                if num_match and float(num_match.group(1)) >= 100:
                                    rec["中标金额"] = raw

                        if rec["标的物名称"] or rec["中标供应商名称"] or rec["中标金额"]:
                            records.append(rec)
                            goods_found = True

                    if goods_found:
                        break

            if not goods_found:
                records.append(base)

        except Exception:
            records.append(base)

    except Exception as e:
        print(f"  Detail page error: {e}")
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"{url}\t{str(e)}\n")
        records.append(base)

    if not records:
        records.append(base)

    return records


def append_to_csv(records, file_path):
    file_exists = os.path.exists(file_path)
    fieldnames = [
        "搜索关键词", "项目名称", "项目编号", "中标供应商名称", "中标供应商地址",
        "中标金额", "标的物名称", "品牌", "规格型号", "数量", "单价",
        "发布时间", "采购人", "代理机构", "链接"
    ]
    with open(file_path, mode="a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for r in records:
            writer.writerow(r)


def main():
    driver = create_driver()
    seen_links = set()
    total_count = 0

    try:
        for kw_idx, keyword in enumerate(KEYWORDS, 1):
            print(f"\n{'='*60}")
            print(f"[{kw_idx}/{len(KEYWORDS)}] Keyword: {keyword}")
            print(f"{'='*60}")

            search_url = (
                f"https://search.ccgp.gov.cn/bxsearch?"
                f"searchtype=2&page_index=1&bidSort=&buyerName=&projectId=&pinMu=&bidType=7"
                f"&dbselect=bidx&kw={quote(keyword)}"
                f"&start_time=2025%3A10%3A31&end_time=2026%3A10%3A31"
                f"&timeType=6&displayZone=&zoneId=&pppStatus=0&agentName="
            )
            driver.get(search_url)
            random_delay()

            for page in range(1, MAX_PAGES_PER_KEYWORD + 1):
                print(f"  Page {page}...")
                list_items = extract_list_page(driver)
                print(f"  Found {len(list_items)} items")

                for idx, item in enumerate(list_items, 1):
                    title = item["标题"]
                    link = item["链接"]

                    if should_exclude(title) or not is_result_announcement(title):
                        continue
                    if link in seen_links:
                        continue
                    seen_links.add(link)

                    print(f"    [{idx}] Extracting: {title[:42]}...")
                    detail_records = extract_detail_page(driver, link, title)

                    for rec in detail_records:
                        rec["搜索关键词"] = keyword
                        rec["发布时间"] = item.get("发布时间", "")
                        rec["采购人"] = item.get("采购人", "")
                        rec["代理机构"] = item.get("代理机构", "")

                    for rec in detail_records:
                        amount = rec.get("中标金额", "")
                        company = rec.get("中标供应商名称", "")
                        if not amount and not company:
                            print(f"      Warning: key fields missing -> {link}")
                        else:
                            print(f"      OK | Amount: {amount or 'N/A'} | Supplier: {(company or 'N/A')[:22]}")

                    append_to_csv(detail_records, CSV_FILE)
                    total_count += len(detail_records)
                    time.sleep(random.uniform(1.8, 3.5))

                try:
                    next_btn = driver.find_element(By.CSS_SELECTOR, "a.next")
                    if "disabled" in (next_btn.get_attribute("class") or ""):
                        print("  Reached last page")
                        break
                    next_btn.click()
                    random_delay()
                except Exception:
                    print("  No next page or pagination failed")
                    break

        print(f"\nDone! Total records written: {total_count}")
        print(f"Output file: {CSV_FILE}")
        if os.path.exists(ERROR_LOG):
            print(f"Error log: {ERROR_LOG}")

    except Exception as e:
        print(f"Program error: {e}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
