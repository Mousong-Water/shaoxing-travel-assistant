"""
ScraperHub 全量采集脚本
================================
运行: python run_crawler_center.py
产出: output/ 下按分类的CSV + SQLite数据库
"""

import sys
from pathlib import Path

# 确保导入路径正确
sys.path.insert(0, str(Path(__file__).parent))  # Shaoxing_Travel_Crawler/
sys.path.insert(0, str(Path(__file__).parent.parent))  # D:\Shaoxing_Travel\

from scrapers.gov_api_scraper import GovApiScraper
from scrapers.baike_scraper import BaikeScraper
from scrapers.dianping_scraper import DianpingScraper
from scrapers.mafengwo_scraper import MafengwoScraper
from scrapers.local_news_scraper import LocalNewsScraper
from scrapers.wenglv_scraper import WenglvScraper
from scrapers.weixin_search import WeixinStaticGuides
from data_verifier.cross_validator import CrossValidator, FactChecker
from data_classifier.content_classifier import ContentClassifier
from data_merger.csv_writer import write_to_csv, write_summary_csv
from data_merger.db_writer import write_to_sqlite

# ============================================================
# Step 1: 采集全部数据源
# ============================================================
print("=" * 60)
print("  ScraperHub 全量数据采集")
print("=" * 60)

raw = {}

# 1. 政府API (10个官方景点)
print("\n[gov_api] 绍兴公共数据开放平台...")
raw['gov_api'] = GovApiScraper().run()
print(f"  → {len(raw['gov_api'])} 条")

# 2. 百度百科 (25个景点文化背景)
print("\n[baike] 百度百科...")
raw['baike'] = BaikeScraper(max_items=25).run()
print(f"  → {len(raw['baike'])} 条")

# 3. 大众点评 (美食店铺)
print("\n[dianping] 大众点评美食...")
raw['dianping'] = DianpingScraper().run()
print(f"  → {len(raw['dianping'])} 条")

# 4. 马蜂窝 (游记攻略)
print("\n[mafengwo] 马蜂窝攻略...")
raw['mafengwo'] = MafengwoScraper().run()
print(f"  → {len(raw['mafengwo'])} 条")

# 5. 本地新闻
print("\n[local_news] 绍兴新闻网...")
raw['local_news'] = LocalNewsScraper().run()
print(f"  → {len(raw['local_news'])} 条")

# 6. 浙江文旅厅
print("\n[wenglv] 浙江文旅厅...")
raw['wenglv'] = WenglvScraper().run()
print(f"  → {len(raw['wenglv'])} 条")

# 7. 微信文章 (静态数据)
print("\n[weixin] 搜狗微信...")
raw['weixin'] = [
    {
        '标题': t['主题'],
        '内容摘要': t['内容摘要'],
        '时间': t.get('时间', ''),
        '_data_category': t['_data_category'],
        '_trust_level': 1,
    }
    for t in WeixinStaticGuides.COMMON_TOPICS
]
print(f"  → {len(raw['weixin'])} 条")

total = sum(len(v) for v in raw.values())
print(f"\n{'='*60}")
print(f"  采集总计: {total} 条 ({len(raw)} 个数据源)")
print(f"{'='*60}")

# ============================================================
# Step 2: 交叉验证
# ============================================================
print("\n[验证] 多源交叉验证...")
validator = CrossValidator()
verified = validator.validate(raw)

trust_dist = {}
for r in verified:
    t = r.get('信任等级', 0)
    trust_dist[t] = trust_dist.get(t, 0) + 1

print(f"  合并后: {len(verified)} 条")
print(f"  信任分布: L4={trust_dist.get(4,0)} L3={trust_dist.get(3,0)} L2={trust_dist.get(2,0)} L1={trust_dist.get(1,0)}")

# 事实检查
issues_found = 0
for r in verified:
    for issue in FactChecker.check_spot_data(r):
        issues_found += 1
        name = r.get('名称') or r.get('店名') or r.get('标题') or r.get('景点') or r.get('线路名') or '?'
        print(f"  ⚠ {name}: {issue}")
print(f"  事实问题: {issues_found} 条")

# ============================================================
# Step 3: 分类
# ============================================================
print("\n[分类] 内容自动分类...")
classified = ContentClassifier().classify(verified)
for cat, items in sorted(classified.items()):
    samples = []
    for item in items[:3]:
        name = item.get('名称') or item.get('店名') or item.get('标题') or item.get('景点') or item.get('线路名') or '?'
        samples.append(name[:25])
    print(f"  [{cat}]: {len(items)} 条 — {', '.join(samples)}")

# ============================================================
# Step 4: 导出
# ============================================================
print("\n[导出] CSV + SQLite...")
csv_dir = Path(__file__).parent / 'output'
csv_dir.mkdir(parents=True, exist_ok=True)

csv_files = write_to_csv(classified, csv_dir)
summary_path = write_summary_csv(classified, csv_dir / 'all_data_summary.csv')
db_path = write_to_sqlite(classified)

print(f"\n  CSV文件 ({len(csv_files)} 个):")
for cat, path in csv_files.items():
    print(f"    {path.name}")
print(f"  汇总: {summary_path.name}")
print(f"  SQLite: {db_path}")

print(f"\n{'='*60}")
print(f"  ✓ 全流程完成!")
print(f"  数据文件在: {csv_dir}")
print(f"{'='*60}")
