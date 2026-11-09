<img width="1122" height="584" alt="功率器件相关中标市场考察" src="https://github.com/user-attachments/assets/70afd36a-1449-400b-977a-099cb671370b" />

# B2B-Market-Insight-Dashboard

Power Device / Semiconductor Bidding Market Insight Project

## Project Overview
Collected and analyzed public procurement (中标) data related to power devices, semiconductors, IGBT, SiC, GaN, etc. from China Government Procurement website, to support competitor analysis and sales lead prioritization.

## Key Features
- **Data Collection**: Python + Selenium crawler with multi-keyword search, list page + detail page extraction
- **Data Cleaning**: Unified currency units (万元 → 元), handled outliers & duplicates with Pandas
- **Visualization**: Tableau dashboard covering:
  - Bid amount distribution
  - Supplier Top 10
  - Keyword market size
  - Time trend analysis

## Tech Stack
- Python 3
- Selenium + webdriver-manager
- Pandas
- Tableau

## Project Structure
├── scraper.py          # Main crawler script
├── data_cleaning.py    # Amount unification & deduplication
├── README.md
└── screenshots/        # Dashboard images

## How to Run (Scraper)
1. Install dependencies:
```bash
pip install selenium webdriver-manager pandas
```
