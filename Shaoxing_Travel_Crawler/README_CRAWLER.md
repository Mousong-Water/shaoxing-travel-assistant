# 绍兴智能旅游助手 — 爬虫系统使用说明

## 一、数据模式

```
┌─────────────────────────────────────────────────────┐
│                    数据来源                           │
├───────────────┬──────────────┬──────────────────────┤
│  静态数据      │  动态爬虫     │  综合生成器           │
│  (JSON预置)    │  (实时抓取)   │  (JSON→多维度展开)    │
├───────────────┼──────────────┼──────────────────────┤
│ 百度百科 16条  │ 携程 Playwright│ 景点 76→456条        │
│ 大众点评 18条  │ 小红书 Playwright│ 美食 88→352条      │
│ 马蜂窝 12条   │ 知乎 搜索页   │ 文化 38→76条          │
│ 政府API 10条  │ 文旅官网      │ 住宿 28→56条          │
│ 微信 4条      │ 本地新闻      │ 购物 16→32条          │
│ 新闻 3条      │              │ 研学 21→21条          │
│ 文旅厅 3条    │              │                      │
└───────────────┴──────────────┴──────────────────────┘
```

**静态优先、动态补充**：所有爬虫默认使用静态预置数据（`comprehensive/*.json`），设置 `source_mode='dynamic'` 或 `use_playwright=True` 才会触发实时抓取。

**重复运行安全**：每次运行生成的文件名为 `*_latest.csv`，自动覆盖上一次结果。SQLite 通过 `source_url` 唯一键去重写入。

---

## 二、运行流程

```
python run_crawler_center.py

Phase A ──→ 传统爬虫采集 (7个源, ~66条)
Phase B ──→ 综合数据生成器 (8个JSON → ~1000条多维数据)
Phase C ──→ 小红书 + 知乎 (30条)
Phase D ──→ 交叉验证 (多源一致性检查, 信任度评分)
Phase E ──→ 内容分类 (9大类自动归类)
Phase E2──→ 实体合并引擎 (名称+距离+分类 三重校验)
Phase F ──→ 导出 (entities_latest.csv + contents_latest.csv + SQLite)
```

### 各Phase详解

| Phase | 输入 | 处理 | 输出 |
|-------|------|------|------|
| A | 7个静态爬虫 | 返回结构化字典列表 | raw dict |
| B | 8个JSON数据文件 | DataGenerator 展开为多维条目 | 约1000条记录 |
| C | XHS+知乎爬虫 | 静态回退/Playwright可选 | 约30条 |
| D | 传统爬虫数据 | CrossValidator 多源交叉验证 | 带信任等级的数据 |
| E | 全部数据 | ContentClassifier 正则分类 | 9个分类桶 |
| E2 | 分类数据 | EntityMerger 实体/内容分离+合并 | entities + contents |
| F | 实体+内容 | CSV导出+SQLite入库 | output/ 目录 |

### 产出文件

```
output/
├── entities_latest.csv          ← 实体表 (景点/酒店/店铺/非遗)
├── contents_latest.csv          ← 内容表 (攻略/笔记/活动/路线)
├── all_data_summary_latest.csv  ← 全量汇总
└── *_latest.csv                 ← 各分类独立CSV
```

---

## 三、数据去重与合并机制

### 3.1 单次运行内的去重

```
                   ┌─────────────┐
  多源原始数据 →    │ CrossValidator │ → 按名称合并多源数据
                   └─────────────┘
                          │
                   ┌──────▼──────┐
                   │ EntityMerger │ → 名称相似度>0.75
                   │              │   + 地理距离<500m
                   │              │   + 分类一致
                   │              │   = 合并为同一实体
                   └─────────────┘
```

### 3.2 跨运行去重 (SQLite)

```sql
-- 写入时通过 source_url 唯一键自动去重
INSERT INTO attractions (...) VALUES (...)
ON CONFLICT(source_url) DO UPDATE SET ...  -- 更新已有记录
```

### 3.3 实体合并规则

| 条件 | 阈值 | 说明 |
|------|------|------|
| 名称相似度 | > 0.75 | 使用 SequenceMatcher |
| 地理距离 | < 500m | Haversine公式 |
| 分类一致 | 必须相同 | 景点/美食/非遗/展馆 |

**示例**：`鲁迅故里` 和 `鲁迅故居` 会被合并，`鲁迅故里` 和 `鲁迅外婆家` 不会（距离10km > 500m）。

### 3.4 字段合并优先级

```
官方网站 > 马蜂窝 > 大众点评 > 携程 > 小红书 > 百度百科
```

- 评分：多源加权平均
- 简介：取最完整
- 开放时间/门票：取最高优先级来源
- 图片URL：全部收集去重

---

## 四、信任等级体系

| 等级 | 条件 | 颜色 |
|------|------|------|
| L4 | 政府/官方数据确认 | 🟢 权威 |
| L3 | 3+独立源一致 | 🟢 高可信 |
| L2 | 2源一致 | 🟡 较可信 |
| L1 | 单一来源 | 🟠 仅参考 |
| L0 | 被其他源证伪（冲突） | 🔴 不可信 |

**单源数据不丢弃**：L1 数据保留入库，只在多源冲突时标记备选值。

---

## 五、配置说明

### 5.1 数据源选择

编辑 `run_crawler_center.py` 中的 `Phase A` 列表：

```python
for name, scraper_cls in [
    ("gov_api", GovApiScraper),       # 政府API
    ("baike", BaikeScraper),          # 百度百科
    ("dianping", DianpingScraper),    # 大众点评
    ("mafengwo", MafengwoScraper),    # 马蜂窝
    ("local_news", LocalNewsScraper), # 本地新闻
    ("wenglv", WenglvScraper),        # 文旅厅
]:
```

注释掉不需要的数据源即可。

### 5.2 动态爬虫开关

```python
# 小红书 (默认静态, Playwright模式)
XiaohongshuScraper(use_playwright=False)   # 静态
XiaohongshuScraper(use_playwright=True)    # Playwright动态

# 携程 (render_mode)
CtripScraper(render_mode='auto')        # 请求优先, 被拦截→Playwright
CtripScraper(render_mode='requests')    # 纯requests
CtripScraper(render_mode='playwright')  # 纯Playwright
```

### 5.3 数据量控制

```python
# 每个爬虫独立控制
BaikeScraper(max_items=30)     # 最多30条
DianpingScraper(max_items=50)  # 最多50条
```

---

## 六、新增子爬虫操作指南

### 6.1 创建爬虫文件

在 `scrapers/` 目录新建 `your_scraper.py`，实现 `run()` 方法：

```python
# scrapers/your_scraper.py
"""你的爬虫说明"""
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class YourScraper:
    """你的爬虫描述"""

    def __init__(self, max_items: int = None):
        self.max_items = max_items

    def run(self) -> List[Dict]:
        """
        返回: [dict, dict, ...]
        每个dict必须包含:
          - _data_category: 数据类别 (见下方分类表)
          - _trust_level: 信任等级 (1-4)
          - 来源平台: 统一命名
          - 来源URL: 唯一标识
        """
        results = []

        # 你的采集逻辑
        # ...

        return results[:self.max_items] if self.max_items else results
```

### 6.2 数据分类参考

| _data_category | 含义 | 合并为实体? |
|---------------|------|------------|
| `attraction_basic` | 景点/酒店基础信息 | ✅ 是 |
| `attraction_culture` | 文化背景/非遗 | ✅ 是 (非遗类) |
| `attraction_review` | 游玩攻略/笔记 | ❌ 否 (内容) |
| `food_shop` | 美食店铺 | ✅ 是 |
| `local_food` | 特色小吃/菜品 | ❌ 否 (内容) |
| `seasonal_event` | 时令活动/节庆 | ❌ 否 (内容) |
| `travel_route` | 推荐线路 | ❌ 否 (内容) |
| `official_notice` | 官方公告 | ❌ 否 (内容) |
| `transport_info` | 交通信息 | ❌ 否 (内容) |

### 6.3 返回字段规范

**实体类数据** (会被合并):
```python
{
    "名称": "景点名",           # 必填
    "地址": "详细地址",         # 有则填
    "行政区": "越城区",         # 6区之一
    "开放时间": "08:00-17:00",
    "门票价格": "50元",
    "评分": 4.5,               # float 0-5
    "简介": "描述文本",
    "标签": "5A景区|人文历史",  # |分隔
    "纬度": 30.0,              # 可选, 用于合并
    "经度": 120.5,
    "来源平台": "your_platform",  # 统一命名
    "来源URL": "unique_key",      # 唯一标识用于去重
    "_data_category": "attraction_basic",
    "_trust_level": 2,            # 1-4
}
```

**内容类数据** (独立存储):
```python
{
    "标题": "帖子标题",         # 或 景点/主题
    "内容": "正文摘要",
    "游玩建议": "建议内容",
    "贴士": "提示信息",
    "来源平台": "xiaohongshu",
    "来源URL": "unique_key",
    "_data_category": "attraction_review",
    "_trust_level": 1,
}
```

### 6.4 注册到主流程

在 `run_crawler_center.py` 的 Phase A 中添加：

```python
from scrapers.your_scraper import YourScraper

# 在 Phase A 的 for 循环中添加:
("your_key", YourScraper),
```

### 6.5 添加静态JSON数据 (推荐方式)

如果有大量预置数据，放在 `comprehensive/` 目录：

```json
// comprehensive/your_data.json
[
  {"name": "项目1", "field1": "value1", ...},
  {"name": "项目2", "field1": "value2", ...}
]
```

然后在 `comprehensive/data_generator.py` 中加载并生成：

```python
# 在 __init__ 中:
self.your_data = load_json('your_data.json')

# 在 generate_all 中:
for item in self.your_data:
    results['attraction_basic'].append(self._gen_your_type(item))

# 添加生成方法:
def _gen_your_type(self, item: Dict) -> Dict:
    return {
        "名称": item["name"],
        ...
        "_data_category": "attraction_basic",
        "_trust_level": 3,
    }
```

---

## 七、已有数据源速查

| key | 类名 | 模式 | 数据量 | 文件 |
|-----|------|------|--------|------|
| gov_api | GovApiScraper | 静态 | 10条 | scrapers/gov_api_scraper.py |
| baike | BaikeScraper | 静态 | 16条 | scrapers/baike_scraper.py |
| dianping | DianpingScraper | 静态 | 18条 | scrapers/dianping_scraper.py |
| mafengwo | MafengwoScraper | 静态 | 12条 | scrapers/mafengwo_scraper.py |
| local_news | LocalNewsScraper | 静态+动态 | 3条 | scrapers/local_news_scraper.py |
| wenglv | WenglvScraper | 静态 | 3条 | scrapers/wenglv_scraper.py |
| weixin | WeixinStaticGuides | 静态 | 4条 | scrapers/weixin_search.py |
| xiaohongshu | XiaohongshuScraper | 静态+Playwright | 20条 | scrapers/xiaohongshu_scraper.py |
| zhihu | ZhihuScraper | 静态 | 10条 | scrapers/zhihu_scraper.py |
| ctrip | CtripScraper | Playwright+requests | 动态 | scrapers/ctrip_scraper.py |

### JSON数据文件

| 文件 | 条目数 | 展开维度 | 展开后 |
|------|--------|---------|--------|
| attractions.json | 76 | ×6维 | ~456 |
| foods.json | 88 | ×4维 | ~352 |
| cultures.json | 38 | ×2维 | ~76 |
| accommodations.json | 28 | ×2维 | ~56 |
| shopping.json | 16 | ×2维 | ~32 |
| study_tours.json | 21 | ×1维 | ~21 |
| events.json | 15 | ×1维 | ~15 |
| routes.json | 10 | ×1维 | ~10 |

---

## 八、常见问题

**Q: 重复运行会重复数据吗？**
A: 不会。CSV文件固定命名 `*_latest.csv`，每次运行覆盖。SQLite 通过 `source_url` 唯一键 upsert。

**Q: 如何只更新某一类数据？**
A: 注释掉 `run_crawler_center.py` 中不需要的 Phase，或只保留对应的爬虫。

**Q: 如何切换静态/动态模式？**
A: 修改爬虫的 `source_mode` 参数：`'static'` 仅预置数据，`'dynamic'` 实时抓取，`'auto'` 动态优先降级静态。

**Q: JSON数据在哪里维护？**
A: `comprehensive/*.json`，编辑后重新运行即可。格式：JSON数组，每个元素一个对象。

**Q: 如何新增一个城市？**
A: 目前仅支持绍兴。如需新增，需：1)创建对应JSON数据文件 2)修改爬虫中的城市参数 3)生成器中的地址/行政区信息。
