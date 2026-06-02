# Shaoxing Travel Crawler - 绍兴旅游景点爬虫

## 项目概述
开发一个旅游景点爬虫，目标站点为携程（you.ctrip.com），爬取绍兴旅游景点数据。

## 技术栈
- **Playwright** (有头模式) — 用于列表页，绕过腾讯云WAF反爬
- **requests + BeautifulSoup** — 用于详情页，复用Playwright获取的Cookie
- **CSV (utf-8-sig)** — 数据存储格式

## 当前状态
- [x] 爬虫核心代码已完成: `Shaoxing_Travel_Crawler/shaoxing_scraper.py`
- [x] 已验证爬取3个景点: 柯岩风景区、东湖、兰亭景区
- [x] 混合模式验证成功: Playwright获取Cookie → requests爬详情
- [ ] 数据质量优化（地址/门票/标签字段可进一步精确）

## 关键发现
1. 携程使用腾讯云WAF + JS挑战反爬，纯requests无法访问列表页
2. Playwright有头模式 + 反检测脚本可绕过WAF
3. 携程Cookie可传递给requests复用，详情页响应2MB+
4. 正确URL格式: `you.ctrip.com/sight/shaoxing18/s0-p1.html`
5. 景点链接格式: `you.ctrip.com/sight/shaoxing18/{poi_id}.html`

## 提取字段
名称、城市、地址、开放时间、门票价格、游玩时长、评分、标签、简介、交通

## 关键参数
- LIST_URL: `https://you.ctrip.com/sight/shaoxing18/s0-p1.html`
- MAX_SPOTS: 爬取数量限制
- DELAY: 请求间隔（秒）
- 城市切换: 修改URL中的 `shaoxing18` → 如杭州 `hangzhou14`、北京 `beijing1`

## 文件结构
```
D:\Shaoxing_Travel\
├── CLAUDE.md                          ← 本文件（项目上下文）
├── Shaoxing_Travel_Crawler\
│   ├── shaoxing_scraper.py           ← 爬虫主程序
│   └── shaoxing_attractions_*.csv    ← 爬取结果
└── sessions\
    ├── session_*.jsonl               ← 历史会话原始记录
    └── session_readable.md           ← 历史会话可读版
```

## 待优化
1. 柯岩风景区地址字段含噪音（混入了讲解服务信息）
2. 兰亭门票实际收费但页面显示"免费"
3. 标签和交通字段可增加更精准的CSS选择器
4. 可增加多页爬取、并发控制等功能
