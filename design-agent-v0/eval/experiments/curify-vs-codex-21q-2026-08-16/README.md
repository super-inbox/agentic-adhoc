# Curify vs Codex：21 条 Design Agent 单轮评测

本实验将 `design-agent-bench-v0.1-multimodal-pilot` 的 21 条多模态 query 分别交给
Curify Web 和 Codex CLI，各运行一次，不自动重试。任务覆盖 Brand Identity、Packaging、
Merch、Marketing Creative、Industrial/Product 五类设计工作。

## 候选配置

- Curify：`jwang/vercel@275f7d0a`，本地前端连接已配置的 Curify production API。
- Codex：CLI `0.146.0`，`gpt-5.6-sol`，reasoning `max`，`default` service tier，
  每条使用新的 `--ephemeral` session。
- 两端只收到 dataset 中的 query 和参考图，不收到 hidden rubric、success criteria、
  对方输出或先前评分。

## 生成结果

| Candidate | 正常完成 | 其他状态 | 最终产物 | 输入利用 | 延迟中位数 |
|---|---:|---:|---:|---:|---:|
| Curify Web | 16/21 | 5 partial | 21 | 21/30 assets | 33.754 s |
| Codex CLI | 20/21 | TIQ-098 timeout | 46 | 30/30 assets | 151.270 s |

Curify 当前 UI 只有一个 reference slot，因此 7 条多图任务共遗漏 9 个参考输入；这是产品能力
差异，实验没有人工补偿。runner 根据 plan 估算 Curify 使用 230 credits。Codex 的
TIQ-098 在 15 分钟上限前已经写出 20 个 SKU 图，但尚未完成最终回复与验证，因此严格记录为
`timeout_or_signal`，没有重跑。

Codex 全批 trace 共记录 6,991,464 input tokens（其中 6,226,816 cached）、133,748
output tokens、68,723 reasoning output tokens，以及 53 个 image-tool completion events。
这些是候选运行诊断，不是归一化美元成本。

不依赖视觉 judge 的 deterministic coverage 如下；它只说明输入、文件数量/类型和执行状态，
不能回答哪一端设计得更好：

| Candidate | completed gate | artifact contract | all inputs consumed | production gate | reference utilization mean |
|---|---:|---:|---:|---:|---:|
| Curify Web | 16/21 | 11/21 | 14/21 | 14/21 | 0.8175 |
| Codex CLI | 20/21 | 13/21 | 21/21 | 15/21 | 1.0000 |

## 独立 judge 状态

计划使用 `judge-v2 / gemini-2.5-pro / temperature 0` 做 42 个 blind pointwise judgments。
执行时 Gemini 返回 `429 RESOURCE_EXHAUSTED: monthly spending cap`，所以当前：

- independent visual judge 完成数：`0/42`；
- `weighted_design_mean` 与 `benchmark_total_mean` 均为 `null`；
- `full-comparison.judge-v2.results.jsonl` 只保存 deterministic contract、input、artifact、
  latency 记录和明确的 judge-blocked 原因，不能当作最终视觉质量排名。

候选产物已经冻结。额度恢复后可以只重跑 judge，无需重新消耗 Curify credits 或 Codex
generation usage。

## 文件结构

- `dataset.jsonl`：21 条冻结 dataset；图片路径已改为仓库相对路径。
- `batch-manifest.json`：候选版本、单轮协议和 judge 状态。
- `curify-output-paths.jsonl`：Curify 每条最终输出相对路径、状态、耗时和 omitted roles。
- `candidates/curify/outputs/`：仅保留 Curify 最终输出；按要求不发布页面截图、network log
  或 Curify trajectory。
- `codex-output-and-trajectory-paths.jsonl`：Codex 输出和 trajectory 索引。
- `candidates/codex/runs/<TASK_ID>/`：Codex 最终产物、`trace.jsonl`、最终回复和
  `result.json`；不重复提交输入图。
- `candidates/codex/derived-renders/`：PDF 首屏的 evaluator-derived PNG，仅供查看，
  不计为候选产物。
- `codex-derived-renders.jsonl`：derived render 的来源说明。
- `curify-run-summary.json`、`codex-run-summary.json`：生成阶段聚合。
- `full-comparison.summary.json`、`full-comparison.judge-v2.results.jsonl`：当前评分状态。
- `scripts/`：本轮 runner、judge 和导出脚本的代码快照；不包含凭证。

Codex trace 是可观察的 agent messages、tool calls、command results 和 usage，不包含隐藏的
chain-of-thought。所有本机临时工作目录、Codex home 和 runtime cache 路径都已规范化。
