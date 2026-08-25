# GRAIN & GLOW｜Store Signage Whitespace Reversion v3

状态：**保留 v2 礼盒与淘宝主图；门店立牌留白精确回退到 v1。**

## 客户决定

- 保留 v2 当前礼盒方向；
- 保留 `outputs/v2/01-taobao-main-v2.png`；
- 只把门店立牌恢复为 v1 更疏的留白版本；
- 已删除的价格／促销标签不得恢复。

## 本轮唯一变化

- 来源：`outputs/v1/assets/territory-02-daylight-grain-refined.png`；
- 只取 v1 右侧门店区域中的立牌与陈列，原像素裁切框为 `(1024, 256, 1536, 896)`；
- 原始裁切保存为 `outputs/v3/assets/store-signage-v1-source-crop.png`；
- 4:5 查看稿仅做等比例重采样到 `1200×1500`；
- 没有生成新画面，没有新增文字、Logo、价格、折扣、优惠券或促销组件。

## 保留不动

- v2 淘宝主图的构图、单句卖点与无价格状态；
- 已通过的精装礼盒结构与材料方向；
- B 的色彩、清晨光线、圆形裁切、浅木和天蓝金属系统；
- `outputs/v0`、`outputs/v1`、`outputs/v2` 全部文件。

## 执行方式说明

本次目标是恢复历史版本而不是创作新方案。按保真编辑原则，v3 没有调用生成式图像改写，而是直接复用 v1 已批准像素，避免立牌比例、留白或视觉系统发生漂移。

