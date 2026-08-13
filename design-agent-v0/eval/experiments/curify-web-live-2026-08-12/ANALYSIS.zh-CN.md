# Curify Design Agent 21 条 live 评测分析

## 核心结论

Curify 当前更接近“模板检索 + 单图生成器”，还不是完整的任务执行型 Design
Agent。它能生成视觉上不错的图片，但经常没有真正执行用户指令：16 条可评分结果中，
7 条视觉质量达到 4/5 以上，14/16 的指令遵循得分却为 0，最终 0/21 通过严格
Benchmark。

## 总体结果

| 维度 | 结果 | 解读 |
|---|---:|---|
| 线上运行 | 0 程序错误 | 生成、抓取、附件、Braintrust 链路稳定 |
| 延迟 | 平均 35.3 秒，P95 42.9 秒 | 单图链路在 120 秒预算内 |
| 完成状态 | 16 complete，5 partial | partial 来自多步工具链缺口 |
| Brief adherence | 3.8% | 最大问题：没有完成用户要求 |
| Visual quality | 48.8% | 部分图片有较强模板审美 |
| Refinement ability | 7.5% | 多数“编辑”实际上重新生成或不做修改 |
| Reference gate | 38.1% | 多图任务经常只读取第一张图 |
| Artifact contract | 52.4% | 多方案、批量、生产文件交付不足 |
| Weighted design | 36.2%，`n=16` | 仅覆盖可独立视觉评分的完整输出 |
| Benchmark total | 12.2%，`n=21` | 包含 hard gate 后的全体任务成绩 |
| Pass | 0/21 | 没有一条同时满足全部硬门槛与 70% 阈值 |

## 按能力分析

### 图片编辑：8/8 返回图片，但大多没有真正编辑

平均视觉质量为 47.5%，平均指令遵循只有 5%。典型行为包括：

- “标题放大”返回近似未修改的原图；
- “换背景颜色”生成全新的卡通信息图；
- “移动 Logo”把原设计替换成教育模板；
- 商品精修重新生成产品，而不是保留产品几何、相机角度和版式。

当前 router 把 edit intent 当成模板检索。需要真正的 image-to-image/edit executor，并在
输出后做 source/output diff、产品几何保持和 requested-change verification。

### Design Vote：生成了投票海报，但没有给出模拟投票结果

3 条任务中 2 complete、1 partial；brief adherence 全部为 0，artifact contract 全部
失败。最典型的输出是一张“请用户投票”的精美海报，而任务要求 Agent 自己完成 A–D
排名、赢家、证据和“AI 模拟”声明。

该能力需要独立的 VLM 分析与结构化决策工具，先输出排名/理由 JSON，再确定性渲染图文
报告，不应调用泛模板生成器代替分析。

### Try-on：运行状态 complete，任务语义未完成

4 条均标记为 complete，但 0/4 完整读取输入，0/4 满足多海报交付，平均视觉质量只有
20%。测试中出现绿色卫衣变灰、蓝色 bomber 变黑色皮衣，以及服装任务输出沙发图片。

根因之一是部署页面只接受一张参考图；adapter 只能上传自拍，服装参考被记录为 omitted。
还需要一个能绑定 `person_reference` 与多个 `garment_reference` 的真实 try-on executor。

### SKU variants：最接近成功，但精确计数和色板约束失败

`TIQ-096` 的 weighted design score 为 74.1%，visual quality 为 5/5，是本轮最佳视觉
结果。但任务要求五种颜色，实际只有四种；同时遗漏品牌色板输入，缺少绿色和蓝色，并
保留了色板外的灰色，因此 hard-gated total 为 0。

这说明底层生成质量已经具有可用性，但 runtime 缺少精确 fan-out、输入角色绑定、数量
校验和色板一致性验证。

### Batch 与 factory export：planner 能看到工具，runtime 无法执行

`TIQ-098`、`AR-004`、`AR-010`、`AR-011`、`AR-012` 为 partial。planner 产生了
`compose_grid` 或 `export_print_package`，但 compose step 没有多份上游 artifact，且
`sticker_exporter.py` 仍是本地 Python，不是线上 job/service，因此无法交付 CMYK、刀线、
出血、物理尺寸和生产说明。

这是明确的 product integration/runtime gap，而不是图片模型质量问题。

## 路由层的主要模式

- 简单 edit 指令被路由到 `template-education`；
- vote 指令被路由到 education、MBTI 或包装生成模板；
- try-on 指令被路由到 outfit breakdown，甚至 home textiles；
- factory 指令先生成无关 education 图片，再计划一个无法调用的 export step。

这说明当前执行主干是“检索一个相似模板并填参数”，缺少稳定的 action/capability router。
应先分类 `EDIT / VOTE / TRYON / SKU / FACTORY_EXPORT`，再进入能力专属 planner；低置信度
且没有 executor 时应诚实 abstain，而不是输出看似合理但无关的图片。

## 对评测框架本身的判断

本轮 pipeline 已经证明真实 pixels、线上浏览器执行、step trace、Braintrust attachments、
独立多模态 judge、hard gates 和补跑/合并流程能够端到端工作。但以下指标不能直接用于
外部 Agent 排名：

1. `target_capability_coverage` 当前实际是“complete + 最低文件数”，不是能力语义正确率；
   图片未被编辑也可能得到 100%。建议改名 `task_completion_coverage`。
2. `target_stage_coverage=100%` 会把 failed stage 也计入，代表 trace 可观测性，不代表阶段
   成功。建议拆成 `stage_observability_coverage` 和 `stage_success_rate`。
3. `reference_fidelity_gate` 主要检查是否消费输入，不检查产品/人物视觉忠实度。建议改名
   `reference_consumption_gate`，另设语义 fidelity scorer。
4. `efficiency=100%` 目前只反映延迟和单轮预算；线上产品没有暴露内部 model calls、tokens、
   retries 和 USD cost，因此暂时不适合跨 Agent 比较。
5. `route_accuracy` 为 N/A，因为部署产品没有输出统一的 capability ID。
6. Gemini judge 曾有 1 次漏维度，现已人工 judge-only retry。下一版应使用强制 JSON Schema、
   missing-dimension 自动重试和 retry trace。

此外，本 pilot 只有 21 条、类别分布不均、全部输入为项目自有 AI fixture、每条只跑一次。
它适合定位产品缺口，但不足以支撑 SOTA 或 leaderboard 结论。

## 建议实施顺序

1. 接入真正的 edit executor 和 preservation verifier，直接覆盖 8/21。
2. 支持多图上传、资产角色绑定、fan-out 与多产物聚合，覆盖详情页、SKU 和 try-on 7/21。
3. 实现专用 design-vote 分析/渲染工具，覆盖 3/21。
4. 将 compose 与 factory exporter 服务化，覆盖 batch/factory 路径。
5. 修正上述指标语义，补齐 route、cost、token 和 tool-call telemetry。
6. 用同一 Dataset 跑 canonical backend runtime，与 web 产品计算真实 integration gap。
7. 经 2–3 名设计师盲评校准 judge 后，再扩到五类 × 20 条、每条至少 3 trials，并接入其他
   Agent 做公平对比。
