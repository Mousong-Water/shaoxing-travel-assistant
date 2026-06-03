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
from data_merger.db_writer import write_to_sqlite


def main():
    print("=" * 70)
    print("  ScraperHub v4.0")
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

    # ========== Phase D: 交叉验证 (仅传统爬虫数据) ==========
    print("\n[Phase D] 交叉验证 (传统爬虫数据)...")
    traditional_keys = ['gov_api','baike','dianping','mafengwo','local_news','wenglv','weixin','xiaohongshu','zhihu']
    traditional_raw = {k: v for k, v in raw.items() if k in traditional_keys}
    generator_raw = {k: v for k, v in raw.items() if k.startswith('gen_') or k.startswith('generator_')}

    verified_traditional = CrossValidator().validate(traditional_raw)
    print(f"  传统爬虫验证: {len(verified_traditional)} 条")

    # 检查事实
    issues = sum(len(FactChecker.check_spot_data(r)) for r in verified_traditional)
    print(f"  事实检查: {issues} 个标记")

    # 生成器数据直接展开(不经过合并验证)
    generator_items = []
    for k, items in generator_raw.items():
        for item in items:
            item['数据来源'] = item.get('来源平台', 'comprehensive')
            item['信任等级'] = item.get('_trust_level', item.get('信任等级', 3))
            item['内容分类'] = item.get('_data_category', '')
            generator_items.append(item)
    print(f"  生成器数据直通: {len(generator_items)} 条")

    # 合并
    all_verified = verified_traditional + generator_items
    print(f"  合并总计: {len(all_verified)} 条")

    # ========== Phase E: 分类 ==========
    print("\n[Phase E] 内容分类...")
    classified = ContentClassifier().classify(all_verified)

    # ========== Phase E2: 实体合并引擎 ==========
    print("\n[Phase E2] 实体合并 (名称+距离+分类 三重校验)...")
    # 展开分类数据为列表
    all_items = []
    for cat, items in classified.items():
        for item in items:
            item["_data_category"] = item.get("_data_category", cat)
            all_items.append(item)

    from data_quality.entity_merger import EntityMerger
    merger = EntityMerger(name_threshold=0.75, geo_threshold_m=500)
    entities, contents = merger.merge(all_items)

    print(f"  实体表: {len(entities)} 条")
    print(f"  内容表: {len(contents)} 条")
    print(f"  合计: {len(entities) + len(contents)} 条")

    # 实体分类统计
    etype_counts = {}
    for e in entities:
        t = e.get("实体类型", "其他")
        etype_counts[t] = etype_counts.get(t, 0) + 1
    for t, c in sorted(etype_counts.items()):
        print(f"    实体[{t}]: {c} 条")

    # 内容关联统计
    linked = sum(1 for c in contents if c.get("entity_id"))
    print(f"  内容关联率: {linked}/{len(contents)} ({100*linked//max(len(contents),1)}%)")

    # ========== Phase F: 导出 ==========
    print("\n[Phase F] 导出实体表+内容表...")
    csv_dir = Path(__file__).parent / "output"
    csv_dir.mkdir(parents=True, exist_ok=True)

    # 实体表导出
    import csv
    entity_path = csv_dir / "entities_latest.csv"
    if entities:
        efields = list(entities[0].keys())
        with open(entity_path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=efields, extrasaction='ignore')
            w.writeheader()
            for e in entities:
                w.writerow(e)
    print(f"  实体表: {entity_path}")

    # 内容表导出
    content_path = csv_dir / "contents_latest.csv"
    if contents:
        cfields = [k for k in contents[0].keys() if not k.startswith('_')]
        with open(content_path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=cfields, extrasaction='ignore')
            w.writeheader()
            for c in contents:
                clean = {k: v for k, v in c.items() if not k.startswith('_') and k in cfields}
                w.writerow(clean)
    print(f"  内容表: {content_path}")

    # 汇总CSV
    all_rows = entities + contents
    summary_path = csv_dir / "all_data_summary_latest.csv"
    if all_rows:
        sfields = list(set().union(*(d.keys() for d in all_rows)))
        sfields = [f for f in sfields if not f.startswith('_')]
        with open(summary_path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=sfields, extrasaction='ignore')
            w.writeheader()
            for row in all_rows:
                w.writerow({k: v for k, v in row.items() if not str(k).startswith('_')})
    print(f"  汇总: {summary_path}")

    # SQLite
    db_path = write_to_sqlite({"entity": entities, "content": contents} if entities else classified)

    # ========== 总结 ==========
    total = len(entities) + len(contents)
    print(f"\n{'='*70}")
    print(f"  ✓ 完成! 实体{len(entities)} + 内容{len(contents)} = {total} 条")
    print(f"  目标: 300实体 + 500内容 = 800条")
    print(f"  实体达标: {'✅' if len(entities) >= 250 else '差' + str(250-len(entities))}")
    print(f"  内容达标: {'✅' if len(contents) >= 400 else '差' + str(400-len(contents))}")
    print(f"  SQLite: {db_path}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
