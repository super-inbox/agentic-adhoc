# Curify integration

本目录是 Design Agent v0 的 Curify 接线包。

- `curify_background/app/agent_runtime/`：有界 runtime、typed schemas、
  skill/tool registry、rendering、verification、trace 和 persistence。
- `curify_background/app/routers/design_agent.py`：`POST /design-agent/runs`
  与 `GET /design-agent/runs/{run_id}`。
- `curify_background/tests/test_design_agent_runtime.py`：runtime、API、权限、
  输入安全、重试、费用与 eval 聚合测试。
- `design-agent-v0.patch`：以上新增文件及 `.env.example`、`config.py`、
  `main.py`、`JobType`、router package 的全部 glue changes。

Patch 基于 `super-inbox/curify-studio@9e5ad90` 生成；先用
`git apply --check` 验证目标 checkout。这里保留新增文件快照便于直接 code
review，但它不是完整 Curify backend，不能单独启动 API。
