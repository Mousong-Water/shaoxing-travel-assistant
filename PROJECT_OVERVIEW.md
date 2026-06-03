# 绍兴智能旅游助手 — 项目全貌

> 浙江省国际大学生创新大赛(2026) 人工智能赛道 课题#18
> "基于通用智能体的智能旅游助手开发"

---

## 一、项目架构

```
D:\Shaoxing_Travel\
│
├── 数据层 (100% 完成)
│   ├── Shaoxing_Travel_Crawler/          ← 爬虫体系
│   │   ├── scrapers/                     ← 10个爬虫
│   │   ├── crawler_utils/                ← 公共工具(Request/Parse)
│   │   ├── comprehensive/                ← 8个JSON知识库
│   │   ├── data_verifier/                ← 交叉验证
│   │   ├── data_classifier/              ← 自动分类
│   │   ├── data_merger/                  ← CSV/SQLite导出
│   │   ├── data_quality/                 ← 实体合并引擎
│   │   └── run_crawler_center.py         ← 主入口
│   ├── data_layer/                       ← SQLite存储层
│   │   ├── storage/                      ← Schema + DBManager
│   │   └── scheduler/                    ← 定时更新
│   └── shared/                           ← 公共配置/日志
│
├── 智能体层 (15% 完成)
│   └── agent_layer/
│       └── planning/
│           └── accommodation_scorer.py   ← 住宿推荐引擎 ✅
│       ├── models/                       ← 多模型 (待开发)
│       ├── rag/                          ← RAG检索 (待开发)
│       └── profile/                      ← 用户画像 (待开发)
│
└── 前端层 (0% 完成)
    └── frontend_layer/                   ← Streamlit (待开发)
```

## 二、数据流向

```
                    ┌─────────────────────┐
                    │   run_crawler_center │
                    │    (统一入口)         │
                    └────────┬────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   Phase A+B             Phase C              Phase D-E
   静态生成器             社交平台              验证+合并
        │                    │                    │
  ┌─────┴─────┐      ┌──────┴──────┐      ┌─────┴─────┐
  │ 8个JSON   │      │ 小红书/知乎  │      │CrossValid- │
  │ DataGen   │      │ 抖音Playwright│      │ator+Entity │
  │ ~1000条   │      │ ~100-200条   │      │Merger      │
  └───────────┘      └──────────────┘      └─────┬─────┘
                                                 │
                                     ┌───────────┴───────────┐
                                     │                       │
                              entities_latest.csv    contents_latest.csv
                              (实体表 ~200条)        (内容表 ~400条)
                                     │                       │
                                     └───────────┬───────────┘
                                                 │
                                            SQLite DB
                                    (source_url唯一键去重)
```

## 三、数据规模

### JSON知识库 (8个文件, 284个实体)

| 文件 | 实体数 | 展开维度 | 展开后条目 |
|------|--------|---------|-----------|
| attractions.json | 76 | ×6维(基础/文化/攻略/交通/季节/图片) | ~456 |
| foods.json | 88 | ×4维(店铺+3道菜品) | ~352 |
| cultures.json | 38 | ×2维(文化+节庆活动) | ~76 |
| accommodations.json | 28 | ×2维(基础+入住贴士) | ~56 |
| shopping.json | 16 | ×2维(店铺+产品) | ~32 |
| study_tours.json | 21 | ×1维(研学项目) | ~21 |
| events.json | 15 | ×1维 | ~15 |
| routes.json | 10 | ×1维 | ~10 |

### 10个爬虫数据源

| 爬虫 | 模式 | 数据量 | 技术 |
|------|------|--------|------|
| 携程 Ctrip | Playwright+requests | 动态 | WAF绕过/混合模式 |
| 百度百科 Baike | 静态 | 16条 | 29景点文化背景 |
| 大众点评 Dianping | 静态 | 18条 | 绍兴老字号美食 |
| 马蜂窝 Mafengwo | 静态 | 12条 | 游记攻略 |
| 绍兴公共数据 GovAPI | 静态 | 10条 | 官方景点数据 |
| 小红书 XHS | 静态+Playwright | 20条 | 热门攻略帖 |
| 抖音 Douyin | Playwright优先+缓存 | 93-300条 | 80+关键词搜索 |
| 知乎 Zhihu | 静态 | 10条 | 高赞回答 |
| 文旅厅 Wenglv | 静态 | 3条 | 精品线路 |
| 本地新闻 LocalNews | 静态 | 3条 | 节庆活动 |

## 四、关键设计决策

### 数据层

- **实体/内容分离**: 景点/酒店/店铺 → 合并为实体; 攻略/笔记/评价 → 独立存储为内容
- **三重校验合并**: 名称相似度>0.75 + 地理距离<500m + 分类一致 → 合并为同一实体
- **字段优先级**: 官方网站 > 马蜂窝 > 大众点评 > 携程 > 小红书 > 百科
- **信任等级**: L4(政府确认) > L3(3源一致) > L2(2源) > L1(单源/社交媒体)

### 爬虫设计

- **静态优先、动态补充**: 所有爬虫默认静态JSON，Playwright/requests为可选动态模式
- **分策运行**: `static`(仅JSON生成器) / `dynamic`(仅爬虫采集) / `all`(全量)
- **增量去重**: source_url唯一键upsert, 重复运行不产生重复数据

### 未来扩展

- **新增子爬虫**: 在 scrapers/ 下新建文件, 实现 run() 方法, 在 run_crawler_center.py 注册即可
- **新增JSON知识库**: 在 comprehensive/ 下新建JSON, 在 data_generator.py 添加加载+生成逻辑

## 五、已完成 vs 待完成

```
数据采集与存储     ████████████████████ 100%  ✅
实体合并引擎       ████████████████████ 100%  ✅
交叉验证与分类     ████████████████████ 100%  ✅
数据清洗与去重     ████████████████████ 100%  ✅
住宿推荐评分       ████████████████████ 100%  ✅ (agent层首个模块)
抖音/小红书爬虫    ████████████████████ 100%  ✅
变更追踪表         ████████████████████ 100%  ✅
────────────────────────────────────────────
RAG检索 (ChromaDB) ░░░░░░░░░░░░░░░░░░░░   0%
多模型注册         ░░░░░░░░░░░░░░░░░░░░   0%
路线规划引擎       ░░░░░░░░░░░░░░░░░░░░   0%
用户画像           ░░░░░░░░░░░░░░░░░░░░   0%
智能体协调器       ░░░░░░░░░░░░░░░░░░░░   0%
Streamlit前端      ░░░░░░░░░░░░░░░░░░░░   0%
比赛文档+Demo      ░░░░░░░░░░░░░░░░░░░░   0%
```

## 六、运行方式

```bash
# 全量数据采集
python Shaoxing_Travel_Crawler/run_crawler_center.py

# 仅静态生成器 (快速)
python Shaoxing_Travel_Crawler/run_crawler_center.py static

# 仅爬虫采集
python Shaoxing_Travel_Crawler/run_crawler_center.py dynamic

# 测试住宿推荐
python agent_layer/planning/accommodation_scorer.py
```

## 七、下一步计划

1. **RAG检索管线**: ChromaDB + BGE中文嵌入 + 混合检索
2. **路线规划引擎**: 多因素评分 + 约束求解 + 4种备选路线
3. **Streamlit前端**: 5页面 + 地图可视化 + 对话界面
4. **比赛文档**: 技术方案 + Demo视频 + 模型调用日志
