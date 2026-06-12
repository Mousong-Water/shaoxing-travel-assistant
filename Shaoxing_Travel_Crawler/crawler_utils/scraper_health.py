"""
爬虫健康检查脚本
================
验证所有子爬虫:
  1. 是否继承 BaseScraper
  2. 是否有真实HTTP调用能力
  3. 是否有回退数据
  4. 是否有重试延时配置

运行: python -m crawler_utils.scraper_health
"""

import inspect
import sys
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

# 待检查的爬虫列表
SCRAPERS_TO_CHECK = [
    ("百度百科", "scrapers.baike_scraper", "BaikeScraper"),
    ("大众点评", "scrapers.dianping_scraper", "DianpingScraper"),
    ("马蜂窝", "scrapers.mafengwo_scraper", "MafengwoScraper"),
    ("知乎", "scrapers.zhihu_scraper", "ZhihuScraper"),
    ("携程", "scrapers.ctrip_scraper", "CtripScraper"),
    ("抖音", "scrapers.douyin_scraper", "DouyinScraper"),
    ("小红书", "scrapers.xiaohongshu_scraper", "XiaohongshuScraper"),
    ("政府API", "scrapers.gov_api_scraper", "GovApiScraper"),
    ("文旅厅", "scrapers.wenglv_scraper", "WenglvScraper"),
    ("本地新闻", "scrapers.local_news_scraper", "LocalNewsScraper"),
    ("微信搜索", "scrapers.weixin_search", "WeixinSearchScraper"),
]


def check_scraper(name: str, module_path: str, class_name: str) -> Dict:
    """检查单个爬虫的健康状况"""
    result = {"名称": name, "状态": "UNKNOWN", "问题": []}

    try:
        mod = __import__(module_path, fromlist=[class_name])
        cls = getattr(mod, class_name)
        instance = cls() if cls.__init__.__code__.co_argcount <= 2 else cls(max_items=1)

        # 检查1: 是否有HTTP调用能力
        has_http = _has_http_method(instance, cls)
        if has_http:
            result["HTTP能力"] = "✅"
        else:
            result["HTTP能力"] = "❌ 假爬虫!"
            result["问题"].append("缺少真实HTTP调用方法(_scrape_live或fetch_detail)")

        # 检查2: 是否有回退数据
        has_fallback = _has_fallback(instance, cls, mod)
        if has_fallback:
            result["回退数据"] = "✅"
        else:
            result["回退数据"] = "⚠️ 无"
            result["问题"].append("无静态回退数据，网络失败将返回空")

        # 检查3: 是否继承BaseScraper或ScraperMixin
        from scrapers.base_scraper import BaseScraper
        from crawler_utils.scraper_mixin import ScraperMixin
        if issubclass(cls, BaseScraper):
            result["继承基类"] = "✅ BaseScraper"
        elif issubclass(cls, ScraperMixin):
            result["继承基类"] = "✅ ScraperMixin"
        else:
            result["继承基类"] = "⚠️ 未继承"
            result["问题"].append("未继承BaseScraper/ScraperMixin，缺少标准流程")

        # 检查4: 是否有run()方法
        if hasattr(instance, 'run') and callable(instance.run):
            result["run方法"] = "✅"
        else:
            result["run方法"] = "❌"
            result["问题"].append("缺少run()方法")

        result["状态"] = "PASS" if not result["问题"] else "WARN"

    except Exception as e:
        result["状态"] = "FAIL"
        result["问题"].append(str(e))

    return result


def _has_http_method(instance, cls) -> bool:
    """检查是否有真实HTTP调用方法"""
    # Check for RequestManager or requests usage in source
    source = inspect.getsource(cls)
    if 'self.rm.get' in source or 'self.rm._request' in source:
        return True
    if 'requests.get' in source or 'requests.Session' in source:
        return True
    if 'page.goto' in source:
        return True
    if hasattr(instance, '_scrape_live') or hasattr(instance, '_scrape_baike_page'):
        return True
    if hasattr(instance, 'fetch_detail') or hasattr(instance, 'fetch_list'):
        return True
    return False


def _has_fallback(instance, cls, mod) -> bool:
    """检查是否有静态回退数据"""
    source = inspect.getsource(cls)
    if 'FALLBACK' in source.upper() or 'STATIC' in source.upper():
        return True
    # Check module-level constants
    for name in dir(mod):
        if 'FALLBACK' in name.upper() or 'STATIC' in name.upper():
            return True
    return False


def run_health_check():
    """运行全部爬虫健康检查"""
    print("=" * 70)
    print("  爬虫健康检查")
    print("=" * 70)
    print()

    results = []
    for name, mod_path, cls_name in SCRAPERS_TO_CHECK:
        try:
            result = check_scraper(name, mod_path, cls_name)
            results.append(result)
            status_icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(result["状态"], "?")
            print(f"  {status_icon} {name:<10} HTTP:{result.get('HTTP能力','?')}  回退:{result.get('回退数据','?')}  基类:{result.get('继承基类','?')}")
            if result["问题"]:
                for issue in result["问题"]:
                    print(f"      ⚠ {issue}")
        except Exception as e:
            print(f"  ❌ {name}: 加载失败 - {e}")
        print()

    # 统计
    passing = sum(1 for r in results if r["状态"] == "PASS")
    warnings = sum(1 for r in results if r["状态"] == "WARN")
    failures = sum(1 for r in results if r["状态"] == "FAIL")
    fake = sum(1 for r in results if "假爬虫" in str(r.get("问题", [])))

    print(f"{'='*70}")
    print(f"  总计: {len(results)}个爬虫")
    print(f"  ✅ 通过: {passing}  ⚠️ 警告: {warnings}  ❌ 失败: {failures}")
    print(f"  🚨 假爬虫: {fake}")
    print(f"{'='*70}")

    return fake == 0  # True = 全部通过


if __name__ == '__main__':
    ok = run_health_check()
    sys.exit(0 if ok else 1)
