# ORBIT COFFEE v1 delta 检查清单

状态：**HOLD - 暂不可送印**

本轮仅记录客户明确反馈，不对 approved artwork 做隐含修改。

## 已确认并更新

| 项目 | 状态 | v1 结论 |
|---|---|---|
| 工厂画板 | PASS | `125×205 mm`，已确认包含四边各 `3 mm` bleed。 |
| 成品 Trim | PASS | `119×199 mm`。计算为 `125-6` × `205-6`，与工厂确认一致。 |
| 背面净含量数值 | RECORDED | 客户要求为 `200 g`，已记录为本轮目标值。 |

## 新发现的内容冲突

Approved artwork 的正面现有净含量为 `250 g`。若只在背面加入 `200 g`，同一包装会出现两个不同的净含量数值。

| 项目 | 状态 | 处理 |
|---|---|---|
| 正面现有 `250 g` | LOCKED/UNCHANGED | 本轮没有收到修改正面的明确指令，因此未改。 |
| 背面目标 `200 g` | NOT APPLIED | 已记录，但没有在图稿中落版，避免输出正反矛盾的打样文件。 |
| 其他定稿区域 | PRESERVED | 未改动。 |
| 生产 PDF | NOT GENERATED | 等待净含量一致性确认及既有技术条件补齐。 |

需要明确：**正面现有 `250 g` 是否也同步改为 `200 g`？** 如果不是，请提供正反面最终一致的精确文案。

## 未被本轮反馈解除的既有阻塞

- 输入仍是 `1376×768 px` 的扁平 RGB 展示合成图、无 ICC；正反面单面像素与 `119×199 mm` 成品比例不匹配。
- 未提供可编辑矢量/高分辨率分版生产源文件。
- 未提供工厂 CMYK ICC 配置与总墨量要求。
- 虽然画板和 Trim 尺寸已确认，但正式结构刀模、封边/拉链/热封区、安全区及方向信息仍未提供。

## v1 输出边界

- `approved-artwork_v1-net-content-conflict-annotated.png` 仅标注冲突，不是修改后的包装图稿。
- `orbit-coffee_v1-delta-gate_NOT-FOR-PRODUCTION.pdf` 是一页 DeviceCMYK、300 dpi 的审核报告，不含生产 TrimBox/BleedBox，不得送印。

