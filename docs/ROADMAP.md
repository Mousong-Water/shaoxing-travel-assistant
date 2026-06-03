# 开发路线图 (垂直切片)

> 2026年6月3日 | 通过 grill-with-docs → improve → PRD → to-issues 流程生成

---

## 当前状态

```
数据层     ████████████████████ 100% ✅
Skills     ████████████████████ 100% ✅
住宿评分   ████████████████████ 100% ✅
──────────────────────────────────
RAG检索    ░░░░░░░░░░░░░░░░░░░░   0%
路线规划   ░░░░░░░░░░░░░░░░░░░░   0%
用户画像   ░░░░░░░░░░░░░░░░░░░░   0%
多模型     ░░░░░░░░░░░░░░░░░░░░   0%
协调器     ░░░░░░░░░░░░░░░░░░░░   0%
Streamlit  ░░░░░░░░░░░░░░░░░░░░   0%
文档/Demo  ░░░░░░░░░░░░░░░░░░░░   0%
```

---

## 切片 1: RAG 检索管线 (6h) — 无依赖，优先启动

```
├── 数据: 实体表+内容表 → 文本拼接 → BGE嵌入 → ChromaDB索引
├── 逻辑: 语义检索(70%) + 关键词检索(30%) → 混合排序
├── 前端: 搜索框 → 结果卡片 (景点探索页)
└── 验证: 查"古建筑 免费" → 返回八字桥/书圣故里
```

**文件**:
- `agent_layer/rag/embeddings.py` — BGE模型加载
- `agent_layer/rag/vector_store.py` — ChromaDB集合管理
- `agent_layer/rag/indexing_pipeline.py` — SQLite→向量索引
- `agent_layer/rag/retriever.py` — 混合检索

---

## 切片 2: 用户画像 + 多模型 (6h) — 依赖: 无

```
├── 数据: 用户自由文本输入 → LLM提取 → UserProfile (Pydantic)
├── 逻辑: Claude/GPT/Ollama 三模型注册 → 路由策略
├── 前端: 偏好设置页 (自由文本+表单双模式)
└── 验证: 输入"带家人3天 喜欢自然 不要太累"→ 正确提取天数/兴趣/节奏
```

**文件**:
- `agent_layer/models/model_registry.py` — 统一接口
- `agent_layer/models/claude_client.py` / `gpt_client.py` / `local_client.py`
- `agent_layer/profile/user_profile.py` — Pydantic模型
- `agent_layer/profile/preference_extractor.py` — LLM提取
- `frontend_layer/pages/02_profile_setup.py`

---

## 切片 3: 路线规划引擎 (10h) — 依赖: 切片1, 切片2

```
├── 数据: 用户画像 + RAG检索结果 + 景点经纬度
├── 逻辑: Scoring(5维加权) → Constraint (每日时间约束) → 4路线生成
├── 前端: 路线规划页 (进度条→Tab切换4方案→日视图展开→地图)
└── 验证: 输入"2天 文化游"→ 产出4条不同侧重的2日路线
```

**文件**:
- `agent_layer/planning/scoring.py` — 多因素评分
- `agent_layer/planning/constraint_solver.py` — 时间/地理约束
- `agent_layer/planning/route_planner.py` — 路线生成
- `agent_layer/planning/route_optimizer.py` — 4路线差异化
- `agent_layer/planning/map_service.py` — 高德API封装
- `frontend_layer/pages/03_route_planning.py`

---

## 切片 4: 智能体协调器 (4h) — 依赖: 切片1-3

```
├── 逻辑: 用户意图→画像提取→RAG检索→路线规划→格式化输出
├── 对话: 路线不满意→自然语言反馈→重新规划
└── 验证: 端到端: "我想去绍兴玩3天" → 完整路线+住宿+美食
```

**文件**:
- `agent_layer/orchestrator.py`

---

## 切片 5: Streamlit 前端全貌 (8h) — 依赖: 切片1-4

```
├── 首页: 项目介绍 + 快捷入口
├── 偏好设置: 自由文本+表单 (切片2已做)
├── 路线规划: 核心页面 (切片3已做)
├── 景点探索: RAG搜索+卡片网格 (切片1已做)
├── 数据面板: 数据新鲜度+分类统计
└── 组件: 路线卡片/景点卡片/地图视图/对话界面
```

**文件**:
- `frontend_layer/app.py` — 入口
- `frontend_layer/pages/01_home.py` / `04_spot_explorer.py` / `05_dashboard.py`
- `frontend_layer/components/route_card.py` / `spot_card.py` / `map_view.py` / `chat_interface.py`

---

## 切片 6: 比赛文档 + Demo (4h) — 依赖: 切片1-5

```
├── 技术方案文档 (含架构图)
├── 作品简介
├── Demo视频录制 (5分钟)
├── 模型调用日志
└── 组员分工说明
```

---

## 依赖关系图

```
切片1 (RAG) ──────┐
                   ├──→ 切片3 (路线规划) ──→ 切片4 (协调器) ──→ 切片5 (前端) ──→ 切片6 (文档)
切片2 (画像+模型) ─┘
```

切片1和2可并行开发。预计 **总计38小时，3人团队约4-5天完成**。
