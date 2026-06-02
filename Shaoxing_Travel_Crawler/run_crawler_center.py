"""
ScraperHub v4.0 全量采集 (目标1700+条)
=========================================
python run_crawler_center.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.gov_api_scraper import GovApiScraper
from scrapers.baike_scraper import BaikeScraper
from scrapers.dianping_scraper import DianpingScraper
from scrapers.mafengwo_scraper import MafengwoScraper
from scrapers.local_news_scraper import LocalNewsScraper
from scrapers.wenglv_scraper import WenglvScraper
from scrapers.weixin_search import WeixinStaticGuides
from scrapers.xiaohongshu_scraper import XiaohongshuScraper
from scrapers.zhihu_scraper import ZhihuScraper
from data_verifier.cross_validator import CrossValidator, FactChecker
from data_classifier.content_classifier import ContentClassifier
from data_merger.csv_writer import write_to_csv, write_summary_csv
from data_merger.db_writer import write_to_sqlite
from data_quality.pipeline_v2 import clean_pipeline


def main():
    print("=" * 70)
    print("  ScraperHub v4.0 — 目标1700+条")
    print("=" * 70)

    # ========== Phase A: 传统爬虫 ==========
    print("\n[Phase A] 传统爬虫采集...")
    raw = {}
    for name, scraper_cls in [
        ("gov_api", GovApiScraper),
        ("baike", BaikeScraper),
        ("dianping", DianpingScraper),
        ("mafengwo", MafengwoScraper),
        ("local_news", LocalNewsScraper),
        ("wenglv", WenglvScraper),
    ]:
        try:
            raw[name] = scraper_cls().run()
            print(f"  {name}: {len(raw[name])} 条")
        except Exception as e:
            print(f"  {name}: ERROR - {e}")
            raw[name] = []

    # 微信
    raw["weixin"] = [
        {"标题": t["主题"], "内容摘要": t["内容摘要"], "时间": t.get("时间", ""),
         "_data_category": t["_data_category"], "_trust_level": 1}
        for t in WeixinStaticGuides.COMMON_TOPICS
    ]
    print(f"  weixin: {len(raw['weixin'])} 条")

    # ========== Phase B: 综合数据生成器 ==========
    print("\n[Phase B] 综合数据生成器...")
    from comprehensive.data_generator import DataGenerator
    gen = DataGenerator()
    comp = gen.generate_all()
    gen_total = sum(len(v) for v in comp.values())
    for cat, items in sorted(comp.items()):
        if items:
            print(f"  [{cat}]: {len(items)} 条")
    print(f"  生成器: {gen_total} 条")
    for cat, items in comp.items():
        raw[f"gen_{cat}"] = items

    # ========== Phase C: 小红书+知乎 (新增) ==========
    print("\n[Phase C] 小红书+知乎...")
    for name, scraper_cls in [
        ("xiaohongshu", XiaohongshuScraper),
        ("zhihu", ZhihuScraper),
    ]:
        try:
            raw[name] = scraper_cls().run()
            print(f"  {name}: {len(raw[name])} 条")
        except Exception as e:
            print(f"  {name}: ERROR - {e}")
            raw[name] = []

    # ========== Phase D: 交叉验证 (修复后) ==========
    print("\n[Phase D] 交叉验证 (单源保留L1)...")
    verified = CrossValidator().validate(raw)
    trust = {}
    for r in verified:
        t = r.get("信任等级", 0)
        trust[t] = trust.get(t, 0) + 1
    print(f"  验证后: {len(verified)} 条")
    print(f"  信任: L4={trust.get(4,0)} L3={trust.get(3,0)} L2={trust.get(2,0)} L1={trust.get(1,0)}")

    # 事实检查
    issues = 0
    for r in verified:
        issues += len(FactChecker.check_spot_data(r))
    print(f"  事实检查: {issues} 个标记")

    # ========== Phase E: 分类 ==========
    print("\n[Phase E] 内容分类...")
    classified = ContentClassifier().classify(verified)

    # ========== Phase E2: 数据清洗管线 v2 ==========
    print("\n[Phase E2] 数据清洗 v2 (去重+填字段+统分类)...")
    cleaned = clean_pipeline(classified)

    # ========== Phase F: 导出 ==========
    print("\n[Phase F] 导出...")
    csv_dir = Path(__file__).parent / "output"
    csv_dir.mkdir(parents=True, exist_ok=True)
    csv_files = write_to_csv(cleaned, csv_dir)
    write_summary_csv(cleaned, csv_dir / "all_data_summary_latest.csv")
    db_path = write_to_sqlite(cleaned)

    # ========== 总结 ==========
    total = sum(len(v) for v in cleaned.values())
    print(f"\n{'='*70}")
    print(f"  ✓ 完成! 总计: {total} 条")
    for cat, items in sorted(cleaned.items()):
        print(f"    {cat}: {len(items)} 条")
    print(f"  1700条目标: {'✅ 达标' if total >= 1700 else f'差{1700-total}条'}")
    print(f"  SQLite: {db_path}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
