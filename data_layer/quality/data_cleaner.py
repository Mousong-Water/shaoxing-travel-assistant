"""
数据清洗模块
================================
对爬取的原始数据进行标准化处理:
  - 地址去噪音 (删除讲解服务、卫生间指示等垃圾信息)
  - 门票价格解析 (文本 → 数值)
  - 游玩时长解析 (文本 → 分钟数)
  - 行政区识别 (从地址中提取)
  - 景点分类推断 (从标签/名称推断)
"""

import re
import logging
from typing import Dict, Optional, List, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# 行政区映射
# ============================================================

SHAOXING_DISTRICTS = {
    '越城区': ['越城区', '越城', '老城区', '市区'],
    '柯桥区': ['柯桥区', '柯桥', '绍兴县'],
    '上虞区': ['上虞区', '上虞'],
    '诸暨市': ['诸暨市', '诸暨'],
    '嵊州市': ['嵊州市', '嵊州'],
    '新昌县': ['新昌县', '新昌'],
}

# 地标→行政区 (已知地标映射)
LANDMARK_DISTRICT_MAP = {
    '鲁迅': '越城区', '沈园': '越城区', '东湖': '越城区',
    '书圣': '越城区', '蔡元培': '越城区', '秋瑾': '越城区',
    '周恩来': '越城区', '府山': '越城区', '塔山': '越城区',
    '八字桥': '越城区', '仓桥': '越城区', '百草园': '越城区',
    '三味书屋': '越城区', '咸亨': '越城区', '青藤': '越城区',

    '柯岩': '柯桥区', '兰亭': '柯桥区', '鉴湖': '柯桥区',
    '安昌': '柯桥区', '乔波': '柯桥区', '大香林': '柯桥区',

    '曹娥': '上虞区', '祝家庄': '上虞区', '覆卮山': '上虞区',

    '西施': '诸暨市', '五泄': '诸暨市', '五洩': '诸暨市', '千柱屋': '诸暨市',

    '大佛寺': '新昌县', '穿岩': '新昌县', '天姥': '新昌县', '十九峰': '新昌县',

    '越剧': '嵊州市', '百丈': '嵊州市', '崇仁': '嵊州市',
}

# 分类关键词
CATEGORY_KEYWORDS = {
    '自然风光': ['山', '湖', '江', '河', '溪', '瀑布', '森林', '岩', '洞', '谷',
                '湿地', '峰', '岛', '海', '滩', '温泉', '峡谷', '水乡'],
    '人文历史': ['故居', '故里', '旧址', '遗址', '墓', '陵', '祠', '名人',
                '碑', '塔', '城墙', '古村', '书院',
                '鲁迅', '书法', '越剧', '民俗', '非遗', '帝王', '大禹',
                '陆游', '唐婉', '徐渭', '蔡元培', '秋瑾', '周恩来',
                '西施', '曹娥', '书法', '诗词', '宋代园林'],
    '主题公园': ['乐园', '主题公园', '世界', '欢乐', '冒险', '动物', '海洋'],
    '古镇街区': ['古镇', '老街', '古街', '历史街区', '步行街', '小巷', '弄堂', '直街'],
    '文博场馆': ['博物馆', '纪念馆', '展览馆', '美术馆', '图书馆', '展示'],
    '宗教场所': ['寺', '庙', '庵', '观', '教堂', '清真', '塔林', '大佛', '佛教', '兜率天'],
    '休闲娱乐': ['度假', '温泉', '滑雪', '漂流', '采摘', '农庄', '茶园', '酒庄'],
}


def clean_address(raw_address: str) -> Tuple[str, str]:
    """
    清洗地址字段，去除噪音信息。

    噪音模式:
      - "讲解服务..."  → 删除
      - "卫生间..."    → 删除
      - "售票大厅..."  → 删除
      - "含在门票..."  → 删除

    Args:
        raw_address: 原始地址文本
    Returns:
        (cleaned_address, district) 清洗后地址和识别的行政区
    """
    if not raw_address:
        return '', ''

    # 1. 删除噪音模式
    noise_patterns = [
        r'景区讲解[：:][^。]*',     # 讲解服务信息
        r'人工讲解[^。]*',
        r'卫生间[：:]*[^。]*',       # 卫生间信息
        r'售票大厅[^。]*',
        r'停止售票[^。]*',
        r'含在[^。]*门票[^。]*',      # 门票包含信息
        r'参考价格[：:][^。]*',
        r'地址[：:]',                # 字段名前缀
        r'景区[入园|入口|出口][^。]*',
    ]

    cleaned = raw_address
    for pat in noise_patterns:
        cleaned = re.sub(pat, '', cleaned)

    # 清洗多余空白
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ，,。')

    # 2. 识别行政区
    district = _identify_district(cleaned, raw_address)

    # 3. 如果清洗后太短（<3字符），尝试从原始中提取纯地址
    if len(cleaned) < 3:
        # 提取"绍兴市..."模式
        m = re.search(r'绍兴市[^\s，,。；;]{2,30}', raw_address)
        if m:
            cleaned = m.group(0)

    return cleaned, district


def _identify_district(cleaned_addr: str, raw_addr: str) -> str:
    """
    从地址文本中识别行政区。

    策略:
      1. 直接匹配行政区名
      2. 通过已知地标推断
      3. 默认为越城区
    """
    combined = cleaned_addr + ' ' + raw_addr

    # 直接匹配
    for district, aliases in SHAOXING_DISTRICTS.items():
        for alias in aliases:
            if alias in combined:
                return district

    # 地标推断
    for landmark, district in LANDMARK_DISTRICT_MAP.items():
        if landmark in combined:
            return district

    # 默认越城区 (绍兴主城区)
    return '越城区'


def parse_ticket_price(raw_price: str) -> Tuple[str, Optional[float]]:
    """
    解析门票价格为文本和数值。

    Args:
        raw_price: 原始门票文本 (如 "80元", "免费", "¥120")
    Returns:
        (price_text, price_numeric)
        如: ("80元", 80.0), ("免费", 0.0), ("", None)
    """
    if not raw_price:
        return '', None

    price = raw_price.strip()

    # 免费识别
    if any(w in price for w in ['免费', '不收费', '无需门票', '免票']):
        return '免费', 0.0

    # 提取数值
    nums = re.findall(r'[\d.]+', price)
    if not nums:
        return price, None

    try:
        numeric = float(nums[0])
        # 规范化文本
        if numeric == int(numeric):
            text = f"{int(numeric)}元"
        else:
            text = f"{numeric}元"
        return text, numeric
    except ValueError:
        return price, None


def parse_duration(raw_duration: str) -> Tuple[str, Optional[int]]:
    """
    解析游玩时长为标准格式和分钟数。

    Args:
        raw_duration: 原始时长文本 (如 "1-3小时", "半天", "2小时左右")
    Returns:
        (duration_text, duration_minutes)
        如: ("1-3小时", 120), ("半天", 240)
    """
    if not raw_duration:
        return '', None

    dur = raw_duration.strip()

    # 特殊表达
    if any(w in dur for w in ['半天', '半日']):
        return dur, 240  # 半天 ≈ 4小时

    if '天' in dur and '半天' in dur:
        return dur, 360  # 1.5天 ≈ 6h游览时间

    if any(w in dur for w in ['全天', '一天', '一天']):
        return dur, 480  # 全天 ≈ 8h

    # 提取数字范围 (如 "1-3小时", "2~3小时")
    range_match = re.search(r'(\d+\.?\d*)\s*[-~至到]\s*(\d+\.?\d*)\s*(?:小时|h)', dur)
    if range_match:
        lo = float(range_match.group(1))
        hi = float(range_match.group(2))
        mid = (lo + hi) / 2

        unit = '小时'
        if lo >= 1 and hi >= 1:
            text = f"{lo:.0f}-{hi:.0f}{unit}"
        elif lo < 1:
            mins = int(lo * 60)
            text = f"{mins}分钟"
            return text, int(mid * 60)
        return text, int(mid * 60)

    # 单个数字 (如 "2小时", "3.5小时")
    single_match = re.search(r'(\d+\.?\d*)\s*(?:小时|h)', dur)
    if single_match:
        val = float(single_match.group(1))
        return f"{val}小时", int(val * 60)

    # 分钟格式 (如 "90分钟", "120分钟")
    min_match = re.search(r'(\d+)\s*分钟', dur)
    if min_match:
        mins = int(min_match.group(1))
        if mins >= 60:
            hours = mins / 60
            return f"{hours:.1f}小时", mins
        return f"{mins}分钟", mins

    return dur, None


def infer_category(name: str, tags: str, summary: str) -> str:
    """
    根据景点名称、标签、简介推断分类。

    Args:
        name: 景点名称
        tags: 标签 (|分隔)
        summary: 简介
    Returns:
        分类名称
    """
    combined = f"{name} {tags} {summary}"

    # 按优先级匹配
    priorities = ['人文历史', '自然风光', '文博场馆', '古镇街区',
                  '主题公园', '宗教场所', '休闲娱乐']

    for cat in priorities:
        if cat in combined:
            return cat

    # 关键词匹配
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score > 0:
            scores[cat] = score

    if scores:
        return max(scores, key=scores.get)

    return '其他'


def compute_popularity_score(rating: float, review_count: int) -> float:
    """
    计算综合热度分数 (0-100)。

    公式: 评分位次分(60%) + 评论数位次分(40%)

    Args:
        rating: 评分 (0-5)
        review_count: 评论数
    Returns:
        热度分数 (0-100)
    """
    # 类型安全转换
    try:
        rating = float(rating) if rating else 0.0
    except (ValueError, TypeError):
        rating = 0.0
    try:
        review_count = int(review_count) if review_count else 0
    except (ValueError, TypeError):
        review_count = 0

    # rating占60% + 评论数占40%
    rating_score = (rating / 5.0) * 60 if rating > 0 else 30

    # 评论数归一化 (对数尺度)
    if review_count > 0:
        import math
        review_score = min(math.log(review_count + 1) / math.log(10001), 1) * 40
    else:
        review_score = 10  # 默认给基础分

    return round(rating_score + review_score, 1)


def clean_spot_data(spot: Dict) -> Dict:
    """
    对单个景点数据执行完整清洗。

    Args:
        spot: 原始景点字典 (key为数据库列名)
    Returns:
        清洗后的景点字典 (新增字段已填充)
    """
    # 1. 地址清洗
    raw_addr = spot.get('address', '')
    cleaned_addr, district = clean_address(raw_addr)
    spot['address'] = cleaned_addr
    spot['district'] = district

    # 2. 门票解析
    raw_price = spot.get('ticket_price', '')
    price_text, price_num = parse_ticket_price(raw_price)
    spot['ticket_price'] = price_text
    spot['ticket_numeric'] = price_num

    # 3. 时长解析 (仅当 duration_min 尚未设置时从 duration_raw 解析)
    if not spot.get('duration_min'):
        raw_dur = spot.get('duration_raw', '')
        dur_text, dur_min = parse_duration(raw_dur)
        spot['duration_raw'] = dur_text   # 保留原始
        spot['duration_min'] = dur_min

    # 4. 分类推断
    if not spot.get('category'):
        spot['category'] = infer_category(
            spot.get('name', ''),
            spot.get('tags', ''),
            spot.get('summary', ''),
        )

    # 5. 评分标准化
    rating = spot.get('rating', 0)
    try:
        rating = float(rating) if rating else 0.0
    except (ValueError, TypeError):
        rating = 0.0
    if rating > 5.0:
        spot['rating'] = rating / 20.0  # 可能来自百分比值
    elif 0 < rating <= 1.0:
        spot['rating'] = rating * 5.0   # 可能来自0-1归一化

    # 6. 热度分数
    spot['popularity_score'] = compute_popularity_score(
        spot.get('rating', 0),
        spot.get('review_count', 0),
    )

    # 7. 季节适配推断
    if not spot.get('season_suitable'):
        spot['season_suitable'] = _infer_season(spot)

    # 8. 拥挤程度推断
    if not spot.get('crowd_level'):
        pop = spot.get('popularity_score', 0)
        if pop >= 70:
            spot['crowd_level'] = '高'
        elif pop >= 40:
            spot['crowd_level'] = '中'
        else:
            spot['crowd_level'] = '低'

    return spot


def _infer_season(spot: Dict) -> str:
    """推断景点适宜季节"""
    name_tags = f"{spot.get('name', '')} {spot.get('tags', '')} {spot.get('summary', '')}"

    seasons = []

    # 春季关键词
    if any(w in name_tags for w in ['花', '樱花', '桃花', '油菜花', '郁金香', '兰亭', '竹']):
        seasons.append('春')

    # 夏季关键词
    if any(w in name_tags for w in ['漂流', '水上', '瀑布', '避暑', '荷', '湖', '溪']):
        seasons.append('夏')

    # 秋季关键词
    if any(w in name_tags for w in ['红叶', '桂花', '银杏', '丰收', '采摘']):
        seasons.append('秋')

    # 冬季关键词
    if any(w in name_tags for w in ['雪', '冰', '温泉', '梅', '滑雪']):
        seasons.append('冬')

    # 室内景点不受季节限制
    if any(w in name_tags for w in ['博物馆', '纪念馆', '故居', '寺庙', '故居']):
        return '春夏秋冬'

    if not seasons:
        # 室外默认春秋
        if spot.get('category') in ['主题公园', '休闲娱乐']:
            return '春夏秋冬'
        return '春秋'

    return ''.join(seasons)


def clean_batch(spots: List[Dict]) -> List[Dict]:
    """
    批量清洗景点数据。

    Args:
        spots: 原始景点列表
    Returns:
        清洗后的景点列表
    """
    cleaned = []
    for spot in spots:
        try:
            cleaned.append(clean_spot_data(spot))
        except Exception as e:
            logger.warning(f"清洗失败 [{spot.get('name', '?')}]: {e}")
            cleaned.append(spot)
    logger.info(f"批量清洗完成: {len(cleaned)} 条")
    return cleaned
