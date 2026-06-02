"""
ScraperHub 全量数据采集
================================
数据源: 携程 + 政府API + 百度百科 + 马蜂窝 + 大众点评 + 微信 + 新闻 + 文旅厅
         + 综合数据生成器 (80+景点、100+美食、50+文化)

产出: output/ 下分类CSV + SQLite
运行: python run_crawler_center.py
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
from data_verifier.cross_validator import CrossValidator, FactChecker
from data_classifier.content_classifier import ContentClassifier
from data_merger.csv_writer import write_to_csv, write_summary_csv
from data_merger.db_writer import write_to_sqlite


def main():
    print("=" * 70)
    print("  ScraperHub 全量数据采集 (v3.0 - 综合数据生成器)")
    print("=" * 70)

    # ============================================================
    # Phase A: 静态爬虫采集
    # ============================================================
    print("\n[Phase A] 传统爬虫采集...")
    raw = {}

    try:
        raw['gov_api'] = GovApiScraper().run()
        print(f"  gov_api: {len(raw['gov_api'])} 条")
    except Exception as e:
        print(f"  gov_api: ERROR - {e}")
        raw['gov_api'] = []

    try:
        raw['baike'] = BaikeScraper(max_items=30).run()
        print(f"  baike: {len(raw['baike'])} 条")
    except Exception as e:
        print(f"  baike: ERROR - {e}")
        raw['baike'] = []

    try:
        raw['dianping'] = DianpingScraper().run()
        print(f"  dianping: {len(raw['dianping'])} 条")
    except Exception as e:
        print(f"  dianping: ERROR - {e}")
        raw['dianping'] = []

    try:
        raw['mafengwo'] = MafengwoScraper().run()
        print(f"  mafengwo: {len(raw['mafengwo'])} 条")
    except Exception as e:
        print(f"  mafengwo: ERROR - {e}")
        raw['mafengwo'] = []

    try:
        raw['local_news'] = LocalNewsScraper().run()
        print(f"  local_news: {len(raw['local_news'])} 条")
    except Exception as e:
        print(f"  local_news: ERROR - {e}")
        raw['local_news'] = []

    try:
        raw['wenglv'] = WenglvScraper().run()
        print(f"  wenglv: {len(raw['wenglv'])} 条")
    except Exception as e:
        print(f"  wenglv: ERROR - {e}")
        raw['wenglv'] = []

    try:
        raw['weixin'] = [
            {'标题': t['主题'], '内容摘要': t['内容摘要'],
             '时间': t.get('时间', ''),
             '_data_category': t['_data_category'], '_trust_level': 1}
            for t in WeixinStaticGuides.COMMON_TOPICS
        ]
        print(f"  weixin: {len(raw['weixin'])} 条")
    except Exception as e:
        print(f"  weixin: ERROR - {e}")
        raw['weixin'] = []

    # ============================================================
    # Phase B: 综合数据生成器 (主力数据源)
    # ============================================================
    print("\n[Phase B] 综合数据生成器...")
    from comprehensive.data_generator import DataGenerator
    gen = DataGenerator()
    comprehensive_data = gen.generate_all()

    gen_total = sum(len(v) for v in comprehensive_data.values())
    print(f"  生成数据: {gen_total} 条")
    for cat, items in sorted(comprehensive_data.items()):
        if items:
            print(f"    [{cat}]: {len(items)} 条")

    # 将生成器数据注入raw (包装为爬虫格式)
    for cat, items in comprehensive_data.items():
        raw[f'generator_{cat}'] = items

    # ============================================================
    # Phase C: 交叉验证
    # ============================================================
    print("\n[Phase C] 多源交叉验证...")
    validator = CrossValidator()
    verified = validator.validate(raw)

    trust_dist = {}
    for r in verified:
        t = r.get('信任等级', 0)
        trust_dist[t] = trust_dist.get(t, 0) + 1

    print(f"  合并后: {len(verified)} 条")
    print(f"  信任分布: L4={trust_dist.get(4,0)} L3={trust_dist.get(3,0)} "
          f"L2={trust_dist.get(2,0)} L1={trust_dist.get(1,0)}")

    # 事实检查
    issues_found = 0
    for r in verified:
        for issue in FactChecker.check_spot_data(r):
            if issues_found < 10:
                name = (r.get('名称') or r.get('店名') or r.get('标题')
                        or r.get('景点') or r.get('线路名') or '?')
                print(f"  ⚠ {name}: {issue}")
            issues_found += 1
    if issues_found > 10:
        print(f"  ... 共{issues_found}个问题")
    else:
        print(f"  事实问题: {issues_found} 条")

    # ============================================================
    # Phase D: 分类
    # ============================================================
    print("\n[Phase D] 内容自动分类...")
    classified = ContentClassifier().classify(verified)

    total_classified = sum(len(v) for v in classified.values())
    for cat, items in sorted(classified.items()):
        samples = []
        for item in items[:2]:
            name = (item.get('名称') or item.get('店名') or item.get('标题')
                    or item.get('景点') or item.get('线路名') or '?')
            samples.append(name[:20])
        print(f"  [{cat}]: {len(items)} 条 — {', '.join(samples)}")

    # ============================================================
    # Phase E: 导出
    # ============================================================
    print("\n[Phase E] 导出...")
    csv_dir = Path(__file__).parent / 'output'
    csv_dir.mkdir(parents=True, exist_ok=True)

    csv_files = write_to_csv(classified, csv_dir)
    write_summary_csv(classified, csv_dir / 'all_data_summary_latest.csv')
    db_path = write_to_sqlite(classified)

    print(f"\n  CSV文件 ({len(csv_files)} 个):")
    for cat, path in sorted(csv_files.items()):
        print(f"    {path.name}")

    # ============================================================
    # 汇总
    # ============================================================
    print(f"\n{'='*70}")
    print(f"  ✓ 全流程完成!")
    print(f"  总条目: {total_classified} 条")
    print(f"  数据文件: {csv_dir}")
    print(f"  SQLite: {db_path}")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
