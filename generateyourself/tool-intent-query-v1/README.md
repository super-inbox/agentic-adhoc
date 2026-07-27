# Tool-intent Query Set v1

这是用于 Curify Generate Yourself / tool-intent routing 的离线评估集。数据集包含 100 条自然语言 Query，覆盖品牌、文创和电商设计。它不能被 production matcher、embedding 文档、search aliases 或 runtime prompt 读取。

## 分布

| 维度 | 数量 |
|---|---:|
| 品牌 | 34 |
| 文创 | 33 |
| 电商设计 | 33 |
| 总计 | 100 |

Query 同时覆盖宽泛意图、半结构化任务和明确产物，包含中文、英文与中英混合表达。参考图需求分为 `none`、`optional`、`required`。

| 质量切片 | 分布 |
|---|---|
| 语言 | zh-CN 85 / mixed 12 / en 3 |
| 具体程度 | broad 7 / medium 46 / specific 47 |
| 参考图 | none 55 / optional 36 / required 9 |
| 当前能力覆盖 | direct 35 / adjacent 42 / gap 23 |

## 字段

| 字段 | 说明 |
|---|---|
| `id` | 稳定评估 ID，TIQ-001 至 TIQ-100 |
| `query` | 用户可能输入的原始工具意图 Query |
| `language` | `zh-CN`、`en` 或 `mixed` |
| `theme` | 品牌、文创、电商设计 |
| `tool_intent` | 更细的设计任务分类 |
| `specificity` | `broad`、`medium`、`specific` |
| `reference_image` | 是否需要或可能需要用户上传参考图 |
| `expected_route_intents` | 预期进入的 Generate Yourself broad intents |
| `coverage` | Curify 当前能力覆盖：`direct`、`adjacent`、`gap` |
| `candidate_templates` | 用于人工评估的候选模板，不是 runtime gold route |
| `source_refs` | 本地或公开网页来源索引 |

`candidate_templates` 只用于离线分析：`direct` 表示已有模板可直接承载，`adjacent` 表示模板主题相关但结构或参数不完全匹配，`gap` 表示当前目录缺少可靠能力。它不是固定答案，也不得进入生产召回。

## 来源索引

| Source ref | 来源 |
|---|---|
| `CURIFY_TEMPLATE_CATALOG` | `curify-frontend/public/data/nano_templates.json` 与 `curify-frontend/scripts/configs/template_capability_kb.json` |
| `ZCOOL_PACKAGING` | https://www.zcool.com.cn/work/ZNzE3MDExMTY%3D.html |
| `ZCOOL_ECOM_BRANDING` | https://www.zcool.com.cn/article/ZMTYyMTM1Ng%3D%3D.html |
| `ZCOOL_BRAND_UPGRADE` | https://www.zcool.com.cn/article/ZNTAyMTEy.html |
| `ZCOOL_NEW_CULTURAL` | https://www.zcool.com.cn/article/ZMTM2NzQ1Mg%3D%3D.html |
| `ZCOOL_COCREATE_ECOM` | https://www.zcool.com.cn/article/ZMTMxOTA0OA%3D%3D.html |
| `ZCOOL_MODERN_BRAND` | https://www.zcool.com.cn/article/ZMTU5OTcyOA%3D%3D.html |
| `ZCOOL_GLOBAL_BRAND` | https://www.zcool.com.cn/article/ZMTY1NjE4NA%3D%3D.html |
| `LIBLIB_ECOM_DETAIL` | https://www.liblib.art/modelinfo/704b848dc1804107931c8d534b6165dd |
| `LIBLIB_ECOM_POSTER` | https://www.liblib.art/modelinfo/1ac75486c6bf434b84377a0dea2fc31d |
| `LIBLIB_PRODUCT_RETOUCH` | https://www.liblib.art/modelinfo/c4badb5ef2e940e89e0dd72120416e61 |
| `LIBLIB_CULTURAL_IP` | https://www.liblib.art/modelinfo/b9a80aafe1f744008279799a1dbbe5c2 |
| `LIBLIB_3D_IP` | https://www.liblib.art/modelinfo/09e4c689985643168086f84daa65455f |
| `LIBLIB_NATIONAL_TREND` | https://www.liblib.art/modelinfo/9bd82dfebc03423780b3ae769efafa3e |

外部来源仅用于抽取公开页面中的任务主题和行业表达，例如品牌升级、品牌超级符号、品类会场、主图/详情页、商品重光精修、盲盒/IP/文创周边与国潮包装；数据集没有复制站内作品、模型提示词或长段文案。

## 使用建议

1. 按 `theme` 和 `specificity` 分层报告 recall@k、rerank precision、最终可生成率。
2. 单独统计 `reference_image=required` 的路由准确率，避免文本直出流程误接需要上传图片的任务。
3. 分别报告 `direct`、`adjacent`、`gap`：`gap` 不应因 generic fallback 被误判为已有专用能力。
4. 对 broad Query 检查是否展开到合理的 lifestyle / ecommerce / merch / education 路线；对 specific Query 检查是否避免过度扩展。
