# Design Agent v0 — Spec

_起草 2026-07-29 · 把 Curify 已有的生成能力 + 工作流语料 + 出厂管线 + 评测集，收敛成一个可评测的 Design Agent v0。_

> **一句话**：Design Agent = 一个**规划/决策层（LLM/Agent）**，接收「设计请求（query [+ 参考图]）」→ 理解意图 → 路由到合适的 tool/workflow/template → 生成 → （merch 路径）产出**符合工厂规范的生产文件包**。它是 Section-A/B 模板匹配器 → 完整 agent 的演进，坐在 Curify **生成引擎 + 预印/出厂引擎**之上。参考 `raw/factory-ready-07-29`、`agentic-adhoc/tool-intent-query-v1`。

---

## 1. 架构（Agent Loop）

```text
用户请求  query [+ reference image]
        │
        ▼
① UNDERSTAND  —— Vision + LLM → 结构化 intent / Design Spec
        │        {theme, tool_intent, route_intents[], specificity, has_reference, coverage}
        ▼
② PLAN        —— 从能力语料选 workflow + tools（单步 or 多步 workflow）
        │
        ▼
③ GENERATE    —— query → top-k templates → 图像生成（已有的 §3 LLM matching）
        │        或按 workflow 串多步（抠图→改款→排版→…）
        ▼
④ PRODUCTIONIZE (merch 路径) —— 预印管线 → Design-ready / Manufacturing-ready / Factory package
        │
        ▼
⑤ VERIFY      —— 规则检查（相关性 / coverage / 工厂规范合规）→ 不达标则回到 ②
        │
        ▼
输出：设计资产  或  factory-ready ZIP
```

**两层分工**（出自 factory 讨论）：
- **规划层 = LLM / Agent**：理解、路由、发出结构化指令（JSON），不直接画像素/刀线。
- **执行层 = 确定性引擎**：① 生成引擎（nano / Gemini）② 矢量 / 预印引擎（SVG / CMYK / cutline / ReportLab）③（未来）CAD 内核。

**设计原则**（出自 CodingAgents 哲学 + open-design）：
- **Agent-loop over one-shot** —— 多步取信息、迭代到完成，而非单次 prompt。
- **Tool-mediated execution** —— agent 只能通过带 schema 的工具影响世界（权限门 / 审计 / 有界爆炸半径）。
- **Permission-gated autonomy** —— 高自主 + 明确护栏（尤其触及付费 / 生产 / 外发的动作）。
- **Composable + 一份 design contract** —— 借 open-design 的 `DESIGN.md`：把 **skills（行为）/ templates（渲染范式）/ design-systems（brand-DNA）** 拆成可移植目录，用一份 brand 契约做「唯一事实源」，保证 brand-DNA 一致性。

---

## 2. 能力语料（Agent 能做什么）· inputs a + b

Agent 的「可路由能力」来自一个 **registry**（skills × templates × design-systems）：

| 来源 | 内容 | 现状 |
|---|---|---|
| **`tool-inventory.md`** | 所有工具（生成 / 视频 / 图像） | 已有清单 |
| **工作流 demo** | `client_VC_portfolio/brand_workflow_demo_portfolio.pdf`、`curify_merch.pdf` | PDF，需解析成结构化 workflow |
| **代码化工作流** | Blog 的「table card → 转成 code 渲染」示例 | 一个 workflow 范式（结构化 → 代码渲染） |
| **工作流视频** | `Marketing_media/workflow-{design,ip-design,ecommerce-campaign}-{cn,en}.mp4` | 展示 3 条主 workflow（设计 / IP / 电商） |

**语料增长（input b）**：爬取 / 解析专业站（**ZCool、Liblib.art** 等）→ 抽出「单点工具 + 工作流」→ 映射进 registry。与 [`asset-authority-distribution-inventory.md`](asset-authority-distribution-inventory.md) 的「方向 A（设计数据 / 工作流抓取）」是**同一条数据线**——爬回来的 workflow 直接喂 Design Agent 的能力库。

---

## 3. 生成核心（已存在）· input d

`query → intent → top-k templates（LLM matching）→ 图像生成`。这就是当前 Section A 的匹配 + 生成链路。**v0 不重写它**，而是用 Agent 把它**包起来**：加上①理解、②规划（可多步 workflow）、⑤校验。`expected_route_intents` / `candidate_templates` 的口径与 §5 评测集一致。

---

## 3b. 创意探索（Creative Exploration）—— 「哪款更好？」的决策回路

生成的另一面：客户手里已有 **N 个变体**（一款产品的 4 版包装、一张海报的 3 个方向），要的不是再生成一张，而是**在设计空间里做取舍**。这是设计师跟客户天天在跑的「投票 / 评审」回路，Agent 应当原生支持：

```text
brief + 变体集
  → UNDERSTAND   Vision 读每个变体的设计语言；LLM 命名被评判的「轴」（如 质感 / premium）
  → SEGMENT      LLM 按品类定义可信的消费人群 + 人口权重（男士理容 ≠ 儿童玩具）
  → SIMULATE     每个人群按设计线索给各变体打偏好分（有故事、可复述，不是乱数）
  → AGGREGATE    按人群权重汇总 → 总排名 + 冠军
  → PRESENT      确定性渲染决策图：变体缩略 + 占比 + 冠军高亮 + 分人群拆解；文字克制；带水印
```

**两层分工同样成立**：LLM 规划（定轴 / 定人群 / 分人群偏好推理）；**代码确定性渲染**信息图（PIL，CJK 安全，绝不让 AI 画文字）。

**诚实框架**：模拟 ≠ 真实。图上必须标 `模拟投票 · 加权合成`，并在拿到真实票时可无缝替换。

**基准案例**：`design-agent-v0/benchmarks/creative-exploration/` — 首例 `faceo-packaging-2026-07`（FaCeo 男士洁面泡沫 4 版包装 A/B/C/D → 5 人群模拟 → D 款 43% 胜出）。评测维度：人群合理性 / 推理保真 / 排名可辩护 / 呈现克制 / 可执行的 go 决策。v0 该案例半手工产出（裁图 + 加权面板 + PIL 渲染 `curify-frontend/raw/creative-exploration-07-29/build_vote.py`），Agent 目标是从「brief + 变体图」自动跑完整回路。

---

## 4. 出厂文件（Factory-ready）· input e —— 护城河

**核心命题**：谁能把「效果图（玩具）」变成「工程文件（生产力）」，谁就打通 B2B 闭环、拿到定价权。工厂要的不是高清 PNG，而是**带物理参数的结构化数据 + 确定性**。

**3 层输出**：

| 层级 | Curify 输出 | 例子 |
|---|---|---|
| Design-ready | 高清 / 透明底 / 可编辑 | PNG / SVG / PDF / PSD |
| Manufacturing-ready | 符合具体工艺 | 刀线 / 出血 / 色板 / 尺寸 / 分层 / 白墨 |
| Factory package | 文件 + 参数 + BOM | ZIP：设计文件 + 尺寸 + 材料 + Pantone + 工艺 + Mockup + `spec.pdf` |

**P0 品类 = Sticker + 亚克力 + POD apparel**（最易标准化，最贴现有 Image Tools）。毛绒 / 手办 / 包装往后放。

**预印管线（5 模块，LLM 规划 + 代码执行）**：
1. **资产拆解 & 超分** —— 300DPI 超分 + SAM 抠图（Alpha 图层）+ Potrace 矢量化。
2. **硬编码「工厂模板库」** —— 高频 SKU 预置 die-cut SVG/PDF 模板，代码严格定义 mm 级尺寸 + 安全区 / 出血 / 裁切线。**不让 AI 画刀线**。
3. **程式化排版（JSON 注入）** —— LLM 作 Orchestrator 输出排版 JSON（坐标 / 缩放 / 图层），后端把拆好的图层注入模板 SVG，自动补出血。
4. **RGB → CMYK** —— 挂工业 ICC（Japan Color / US Web Coated），导出前强制转码，锁印刷色。
5. **封装导出** —— ReportLab / 无头浏览器渲染 → 支持图层的高精度 PDF + Production ZIP（见下）。

```text
panda-keychain-production.zip
  01_artwork_front.png  02_artwork_back.png  03_white_ink_layer.pdf
  04_cutline.svg        05_mockup.jpg        06_spec.pdf   # Size/Material/Printing/Hole/Qty/Color
```

**壁垒来源**：不猜工厂标准。找 **5–10 家工厂**（贴纸 / 亚克力 / 印刷 / POD）收「不需要设计师二次处理就能报价/打样」的文件模板 / 刀版规范 / 下单表 → 沉淀成 **Factory Spec → Production Exporter**。呼应 [[project_designer_copilot_prepress_moat]] 与 asset-inventory 的缺口 b（factory guides）。

---

## 5. 评测 & Benchmark · input f

**基准集**：`agentic-adhoc/generateyourself/tool-intent-query-v1/tool_intent_queries.jsonl` —— **100 条 tool-intent query**，schema：
`{id, query, language, theme, tool_intent, specificity(broad/medium/specific), reference_image, expected_route_intents[], coverage(gap/adjacent/…), candidate_templates[], source_refs[]}`。
既有**宽泛**（品牌设计 / 电商设计）也有**具体**（「上传自拍生成不同穿搭的商品试穿海报」），且 `source_refs` 已挂 ZCool / Liblib —— 与 §2 的语料线同源。**这就是 `agentic-generation-benchmark` repo 的数据。**

**4 层 agentic 评测**（承 [[project_visual_intent_routing_eval]]）：

| 层 | 问题 | 指标 |
|---|---|---|
| Routing | 是否路由到对的 intent / template？ | 对 `expected_route_intents` / `candidate_templates` 的准确率 |
| Slot | 是否抽对参数（subject / style / format）？ | slot F1 |
| Task success | 产出物是否真的是所要的？ | 人工 0/1 或 0–5 |
| Multi-turn | 追问下是否保持上下文并纠偏？ | multi-turn score |

**`coverage=gap` 的 query 直接变成模板 / 工具建设排期**（Agent 评测 → 供给侧路线图，闭环）。

**工具**：用 **LangWatch**（或当下对等的 agent-eval / observability，如 Langfuse / Braintrust / Arize-Phoenix）给 Agent loop 埋点——trace 每步（understand/plan/generate/verify）、按上表打分、聚合出 routing 准确率与 coverage 缺口。

---

## 6. 参考（input c）

- **[nexu-io/open-design](https://github.com/nexu-io/open-design)** —— agent-native / model-agnostic，本地 daemon 用 **MCP** 暴露设计能力给任意 coding agent；一份 `DESIGN.md` brand 契约做事实源；skills / templates / design-systems 拆成可移植目录。**借鉴**：registry 的可组合结构 + brand 契约 + MCP 化的工具暴露。
- **[CodingAgents — Foundations & Philosophy](https://bei-bei-wang.github.io/CodingAgents/PartI-Foundations-01-Introduction-Philosophy)** —— agent-loop / tool-mediated / permission-gated 的心智模型。**借鉴**：§1 的 loop 与执行原则。

---

## 7. v0 范围 & 分期

| 阶段 | 交付 |
|---|---|
| **v0（现在）** | ①理解→②路由→③生成（**包住已有 d**）+ ⑤基础校验；接 §5 **评测 harness**（tool_intent_queries + LangWatch，先跑 routing 层）；出厂路径先做 **Sticker**（e 的 Phase 1–2：Image → Editable → cutline/ZIP） |
| **Phase 2** | 语料增长（爬 ZCool/Liblib，input b）；merch 扩到 亚克力 + POD；brand-DNA design contract；Slot/Task-success 评测层 |
| **Phase 3** | **Agent + CAD**（STEP/STL、工业件参数化修改）；多轮 + 供应链连接（打样 / 询价） |

**v0 非目标**：万能 CAD Agent、覆盖全部 merch 品类、完全自主（生产 / 外发动作需权限门）。

---

## 8. 关联

Section-B 演进（[[project_section_b_evolution_options]]）· Omni-Input Launcher 前门（[[project_omni_input_launcher]]，Source→workflow 的 edu/merch/ecom 三管线）· 预印护城河（[[project_designer_copilot_prepress_moat]]）· `agentic-generation-benchmark` repo（本 spec 的评测数据）· asset-inventory 方向 A（语料线）与缺口 b（factory）。

---

## 9. v0 实施快照（2026-08-01）

已在 `../curify_background/app/agent_runtime/` 落地首个后端垂直切片：

- 有界状态机、typed skill/tool registry、capability/abstention、付费权限门；
- `design-vote`：1 张四宫格或 4 张候选图 → 模拟投票 → 确定性 PNG/JSON；
- `tryon-poster`：自拍 `[+ 商品图]` → 1–4 张海报 → 身份/商品/肢体/版式校验；
- deterministic validator + 独立多模态 reviewer；失败时只重做失败产物，最多 0–2 轮；
- `POST /design-agent/runs` + `GET /design-agent/runs/{run_id}`，复用 Project JSON 持久化与私有 GCS；
- 每步 trace（阶段/工具/模型/延迟/费用估计/脱敏摘要/错误）及数据驱动的单轮 black-box eval；
- 运行时/路由/API/权限/输入安全/重试/费用追踪/评测聚合共 13 个隔离测试通过。

当前边界：线上真实图片 benchmark 尚需补齐可合法使用的 source fixtures 并配置 Gemini/GCS；
LangWatch/Langfuse 等外部平台尚未绑定，现阶段以 Project-backed trace + 结构化日志作为
vendor-neutral observability，`eval/runtime_eval.py` 负责聚合 routing accuracy 与 coverage gap；
异步执行目前沿用 FastAPI `BackgroundTasks`，放量前应切到现有 durable worker/queue。
