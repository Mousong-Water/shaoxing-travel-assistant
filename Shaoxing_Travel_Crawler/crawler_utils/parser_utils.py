"""
公共页面解析工具
================================
从 shaoxing_scraper.py 中抽取的通用HTML解析逻辑，所有爬虫共用。
解决短板: #2 #3 (选择器硬编码、提取器不可复用)
"""

import re
import json
from typing import Dict, List, Optional, Callable
from bs4 import BeautifulSoup, Tag


# ============================================================
# 文本清洗 (原 L67-71)
# ============================================================

def clean_text(text: str) -> str:
    """合并空白字符，去除首尾空格"""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ============================================================
# 安全选择器 (原 L73-83)
# ============================================================

def safe_find(soup: BeautifulSoup, selectors: list, default: str = "") -> str:
    """
    按优先级尝试多个CSS选择器提取文本。

    Args:
        soup: BeautifulSoup对象
        selectors: CSS选择器列表, 按优先级排列, 如 ['.address', 'p[class*="addr"]']
        default: 所有选择器无结果时的默认值
    Returns:
        提取到的文本
    """
    for sel in selectors:
        elem = soup.select_one(sel)
        if elem:
            text = clean_text(elem.get_text())
            if text:
                return text
    return default


def safe_find_all(soup: BeautifulSoup, selectors: list, limit: int = None) -> List[Tag]:
    """
    按优先级尝试多个CSS选择器批量提取元素。

    Args:
        soup: BeautifulSoup对象
        selectors: CSS选择器列表
        limit: 最大返回数
    Returns:
        元素列表
    """
    for sel in selectors:
        elems = soup.select(sel)
        if elems:
            return elems[:limit] if limit else elems
    return []


# ============================================================
# 正则提取 (原 L306-356 的多个正则模式)
# ============================================================

def extract_by_patterns(text: str, patterns: List[str]) -> Optional[str]:
    """
    用多个正则模式依次匹配，返回第一个命中。

    Args:
        text: 待匹配文本
        patterns: 正则模式列表, 按优先级排列
    Returns:
        匹配到的文本, 或None
    """
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            result = m.group(0) if m.lastindex is None else m.group(1)
            return clean_text(result)
    return None


# ============================================================
# 字段提取器工厂 (新增 - 解决短板 #2 #3)
# ============================================================

class FieldExtractor:
    """
    字段提取器基类: 选择器列表 + 正则回退模式。
    子类只需定义 _SELECTORS 和 _REGEX_PATTERNS，无需写重复逻辑。

    使用示例:
        class AddressExtractor(FieldExtractor):
            _SELECTORS = ['.address', '[class*="address"]']
            _REGEX_PATTERNS = [r'地址[：:]\s*(.{5,60}?)(?:[\n。]|$)']
    """

    _SELECTORS: List[str] = []
    _REGEX_PATTERNS: List[str] = []

    @classmethod
    def extract(cls, soup: BeautifulSoup, full_text: str = None,
               default: str = "") -> str:
        """
        从页面提取字段: 先尝试CSS选择器, 再正则回退。

        Args:
            soup: BeautifulSoup对象
            full_text: 页面全文 (用于正则匹配)
            default: 默认值
        Returns:
            提取到的文本
        """
        # Step 1: CSS选择器
        result = safe_find(soup, cls._SELECTORS)
        if result:
            return result

        # Step 2: 正则回退
        if full_text and cls._REGEX_PATTERNS:
            result = extract_by_patterns(full_text, cls._REGEX_PATTERNS)
            if result:
                return result

        return default


# ============================================================
# 携程页面专用提取器
# ============================================================

class AddressExtractor(FieldExtractor):
    _SELECTORS = [
        '.address', '.scenicAddress', '.location',
        'span[class*="address"]', 'p[class*="addr"]',
    ]
    _REGEX_PATTERNS = [
        r'地址[：:]\s*(.{5,60}?)(?:[\n。]|$)',
        r'绍兴市.{2,30}(?:路|街|道|镇|村|号|区)',
    ]


class OpenTimeExtractor(FieldExtractor):
    _SELECTORS = [
        '.openTime', '.businessHours', '.openingHours',
        'span[class*="openTime"]', 'div[class*="opening"]',
    ]
    _REGEX_PATTERNS = [
        r'(?:开放时间|营业时间)[：:]\s*(.{5,40}?)(?:[\n。]|$)',
        r'\d{2}:\d{2}\s*[-~至到]\s*\d{2}:\d{2}',
    ]


class TicketExtractor(FieldExtractor):
    _SELECTORS = [
        '.ticketPrice', '.priceText', '.scenicPrice',
        'span[class*="price"]', 'span[class*="ticket"]',
    ]
    _REGEX_PATTERNS = [
        r'(?:门票|票价)[：:]\s*(.{3,30}?)(?:[\n。]|$)',
        r'(免费|¥\s*\d+|￥\s*\d+|\d+\s*元起?)',
    ]


class RatingExtractor(FieldExtractor):
    _SELECTORS = [
        '.gradeScore', '.commentScore', '.scoreText',
        '[class*="scoreNum"]', '.averageScore',
        'span[class*="grade"]', '.starNum',
    ]


class SummaryExtractor(FieldExtractor):
    _SELECTORS = [
        '.summary', '.scenicIntro', '.description',
        'div[class*="intro"]', 'div[class*="desc"]',
    ]


class DurationExtractor(FieldExtractor):
    _REGEX_PATTERNS = [
        r'(?:建议|游玩|参考|游览)(?:时间|时长)[：:]\s*(.{3,20}?)(?:[\n。]|$)',
        r'(\d+[-~]\d+\s*(?:小时|天|分钟))',
        r'([\d.]+\s*(?:小时|天|分钟))',
    ]


class TransportExtractor(FieldExtractor):
    _REGEX_PATTERNS = [
        r'(?:交通|公交)[：:]\s*(.{8,80}?)(?:[\n。]|$)',
        r'(?:乘坐|搭乘|可乘).{3,40}?(?:公交|地铁|巴士|路|线)',
    ]


class TagsExtractor:
    """标签提取 (特殊逻辑: 取多个元素拼接)"""

    _SELECTORS = [
        '[class*="tag"]', '.label-item', '.scenicTag', '.themeTag',
    ]

    @classmethod
    def extract(cls, soup: BeautifulSoup, max_tags: int = 8) -> str:
        tag_elems = safe_find_all(soup, cls._SELECTORS, limit=max_tags)
        if tag_elems:
            tags = [clean_text(t.get_text()) for t in tag_elems
                    if clean_text(t.get_text())]
            return '|'.join(tags)
        return ''


# ============================================================
# JSON-LD 解析 (原 L291-304)
# ============================================================

def extract_jsonld(soup: BeautifulSoup) -> Optional[Dict]:
    """
    从页面中提取JSON-LD结构化数据。

    Returns:
        解析后的dict, 或None
    """
    for script in soup.find_all('script', type='application/ld+json'):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return None


def fill_from_jsonld(soup: BeautifulSoup, result: Dict[str, str]):
    """
    从JSON-LD中补充地址和评分信息 (原 L291-304 的逻辑)。

    直接修改 result 字典。
    """
    data = extract_jsonld(soup)
    if not data:
        return

    # 地址
    if not result.get('地址'):
        addr = data.get('address', {})
        if isinstance(addr, dict):
            result['地址'] = addr.get('streetAddress', '')
        elif isinstance(addr, str):
            result['地址'] = addr

    # 评分
    if not result.get('评分'):
        agg = data.get('aggregateRating', {})
        if isinstance(agg, dict):
            try:
                result['评分'] = str(agg.get('ratingValue', ''))
            except (ValueError, TypeError):
                pass


# ============================================================
# 景点链接解析 (原 L139-172)
# ============================================================

def parse_attraction_links(
    soup: BeautifulSoup,
    url_pattern: str = r'/sight/(?:shaoxing18|18)/(\d+)\.html',
    base_domain: str = 'https://you.ctrip.com',
) -> List[Dict[str, str]]:
    """
    从列表页HTML中解析景点名称和URL。

    Args:
        soup: BeautifulSoup对象
        url_pattern: 景点URL的正则模式
        base_domain: 基础域名(用于拼接相对URL)
    Returns:
        [{'name': str, 'url': str}, ...]
    """
    attractions = []
    seen_urls = set()   # 短板 #6 修复: URL去重替代纯名称去重

    for a in soup.find_all('a', href=True):
        href = a['href']
        m = re.search(url_pattern, href)
        if not m:
            continue

        name = clean_text(a.get_text())
        if not name or len(name) < 2:
            continue
        if re.match(r'^[\d\s.,;:!?\-]+$', name):
            continue

        # 标准化URL
        if href.startswith('//'):
            full_url = f"https:{href.split('?')[0]}"
        elif href.startswith('http'):
            full_url = href.split('?')[0]
        else:
            full_url = f"{base_domain}{href.split('?')[0]}"

        # URL去重 (解决短板 #6)
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        attractions.append({'name': name, 'url': full_url})

    return attractions
