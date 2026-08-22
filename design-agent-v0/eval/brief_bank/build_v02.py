#!/usr/bin/env python3
"""Build Brief Bank v0.2 from the frozen v0.1 business briefs.

v0.2 does not add new business jobs. It adds an evaluation protocol for the
designer-feedback failure modes: divergent exploration, multi-turn revision,
state recovery, explicit reference roles, editable-object evidence, and
zero-shot/reference/personalized context ablations.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "briefs.v0.1.jsonl"
DEFAULT_OUTPUT = HERE / "briefs.v0.2.jsonl"

DEEP_REVISION_IDS = {
    "DAB-L4-BID-001",
    "DAB-L4-CAM-003",
    "DAB-L4-PSF-003",
    "DAB-L4-ECO-003",
    "DAB-L4-MFA-003",
    "DAB-L4-CFR-001",
    "DAB-L4-CFR-003",
    "DAB-L4-CFRY-002",
}
EXPLORATION_IDS = {
    "DAB-L4-BID-001",
    "DAB-L4-BID-003",
    "DAB-L4-CAM-001",
    "DAB-L4-PSF-001",
    "DAB-L4-ECO-001",
    "DAB-L4-RTO-001",
}
STRUCTURED_EDIT_IDS = {
    "DAB-L3-CAM-002",
    "DAB-L3-MFA-001",
    "DAB-L4-MFA-002",
    "DAB-L3-CFR-002",
    "DAB-L4-CFR-003",
    "DAB-L4-RTO-003",
}
CONTEXT_ABLATION_IDS = {
    "DAB-L4-BID-001",
    "DAB-L4-CAM-001",
    "DAB-L4-ECO-001",
    "DAB-L4-RTO-001",
}

EXPLORATION_QUERY_REWRITES = {
    "DAB-L4-BID-001": (
        "客户说上一版太像小红书模板了，但又不能做得太老气，现有 Logo 不改。附件三个参考品牌风格并不一致。"
        "请先整理冲突，用文字或低成本缩略图展开 8–12 个假设，再聚类成 3 个真正不同的 Creative Territories，"
        "说明每个方向如何回应 brief，等我选择后再深化；周五提案，后面还要延展淘宝主图和门店物料。"
    ),
    "DAB-L4-BID-003": (
        "我们是做工业传感器的，旧视觉太像 2015 年的 SaaS。Logo 轮廓必须保留，但可以整理字标；主色继续用深蓝，"
        "不能做成赛博朋克。销售要技术感，CEO 又说不要冷冰冰。请先用文字或低成本缩略图展开 8–12 个假设，"
        "聚类成 3 个可解释的 Creative Territories，等我选择后再做中英文字标规范、官网 hero 和展会背板。"
    ),
    "DAB-L4-CAM-001": (
        "我们要上线一款夜间香氛，品牌板和产品图都在附件。核心卖点是安静、低刺激、睡前仪式感，不要做成医疗助眠广告。"
        "请先展开 8–12 个低成本 KV 假设，聚类为 3 个差异清楚的 Creative Territories，等内部选择后再完成官网 hero、"
        "Instagram 竖版和邮件头图；Logo、米白底色和陶土红必须沿用。"
    ),
    "DAB-L4-PSF-001": (
        "MORI 基础款包装已经通过，结构、Logo 和信息层级都不要动。请把它延展成茉莉、乌龙、白桃、桂花、青柠五个 SKU。"
        "先展开 8–12 个低成本色彩编码假设，再聚类为 3 个系列策略供我选择；每个口味要一眼能区分，"
        "但放在货架上必须还是同一家，选择后再展开完整系列。"
    ),
    "DAB-L4-ECO-001": (
        "附件是蓝绿色便携音箱白底图和 MORI 品牌板。新品卖点是 12 小时续航、防泼水、可挂包。"
        "请先展开 8–12 个低成本场景假设，聚类为 3 个差异清楚的 Creative Territories，等我选择后再做天猫主图、"
        "三张卖点图、详情页首屏和一张社媒场景海报；产品外观、接口和 Logo 不能变。"
    ),
    "DAB-L4-RTO-001": (
        "我们要给陶土红香薰机做新品详情页。参考 1 取大留白和信息节奏，参考 2 取暖色系统，参考 3 只取大胆几何构图；"
        "不要复制任何品牌、文字或具体图形。请先拆解参考，再展开 8–12 个低成本原创假设，聚类为 3 个 Creative Territories，"
        "等我选择后完成首屏和两张卖点模块。"
    ),
}

ZERO_SHOT_OPTIONAL_INPUTS = {
    "DAB-L4-BID-001": {"reference-a", "reference-b", "reference-c"},
    "DAB-L4-CAM-001": {"brand-board"},
    "DAB-L4-ECO-001": {"brand-board"},
    "DAB-L4-RTO-001": {"layout-ref", "palette-ref", "geometry-ref"},
}

ZERO_SHOT_QUERIES = {
    "DAB-L4-BID-001": (
        "客户说上一版太像小红书模板了，但又不能做得太老气，现有 Logo 不改。只根据现有 identity 和品牌事实，"
        "先展开 8–12 个低成本假设，聚类为 3 个不同的 Creative Territories，说明取舍，等我选择后再准备淘宝主图和门店物料。"
    ),
    "DAB-L4-CAM-001": (
        "我们要上线一款夜间香氛，产品图和已批准文案在附件。核心卖点是安静、低刺激、睡前仪式感，不要做成医疗助眠广告。"
        "在没有额外视觉参考的情况下，先展开 8–12 个低成本 KV 假设，聚类为 3 个方向，等内部选择后再完成官网 hero、"
        "Instagram 竖版和邮件头图。"
    ),
    "DAB-L4-ECO-001": (
        "附件是蓝绿色便携音箱白底图和已批准卖点：12 小时续航、防泼水、可挂包。不要改变产品外观、接口和颜色。"
        "在没有额外风格参考的情况下，先展开 8–12 个低成本场景假设，聚类为 3 个方向，等我选择后再完成六张电商与社媒资产。"
    ),
    "DAB-L4-RTO-001": (
        "请为附件中的陶土红香薰机设计原创新品详情页。不要借用其他品牌、文字或具体图形。先根据产品与批准文案展开"
        " 8–12 个低成本假设，聚类为 3 个 Creative Territories，等我选择后再完成首屏和两张卖点模块。"
    ),
}

PREFERENCE_MEMORY = {
    "DAB-L4-BID-001": {
        "scope": "project",
        "source": "simulated_prior_sessions",
        "accepted_signals": ["克制留白", "礼盒需要高级而非促销感", "保留现有 Logo"],
        "rejected_signals": ["小红书模板感", "过度复古", "高饱和装饰字"],
    },
    "DAB-L4-CAM-001": {
        "scope": "project",
        "source": "simulated_prior_sessions",
        "accepted_signals": ["真实接触面", "柔和侧光", "低刺激的夜间氛围"],
        "rejected_signals": ["医疗助眠暗示", "悬浮产品", "过强霓虹光"],
    },
    "DAB-L4-ECO-001": {
        "scope": "project",
        "source": "simulated_prior_sessions",
        "accepted_signals": ["城市通勤场景", "克制光影", "更多留白"],
        "rejected_signals": ["金色高级感套路", "装饰字过多", "改变产品蓝绿色"],
    },
    "DAB-L4-RTO-001": {
        "scope": "project",
        "source": "simulated_prior_sessions",
        "accepted_signals": ["大胆但原创的弧形构图", "陶土颗粒语言", "清晰信息节奏"],
        "rejected_signals": ["复刻参考品牌", "照搬 SUMMER FORM 几何", "替换产品外观"],
    },
}

DEEP_FIRST_CHECKPOINT = {
    "DAB-L4-BID-001": "select",
    "DAB-L4-CAM-003": "adapt",
    "DAB-L4-PSF-003": "clarify",
    "DAB-L4-ECO-003": "compose",
    "DAB-L4-MFA-003": "clarify",
    "DAB-L4-CFR-001": "interpret",
    "DAB-L4-CFR-003": "review",
    "DAB-L4-CFRY-002": "clarify",
}

DEEP_FOLLOWUPS = {
    "DAB-L4-BID-001": [
        {
            "after_checkpoint": "converge",
            "message": "礼盒方向通过。淘宝主图里的价格标签太促销，只删价格标签并把卖点缩成一句；礼盒和视觉系统不要重做。",
            "expected_changes": ["仅修改淘宝主图价格标签和卖点层级", "保留已通过礼盒方向"],
            "invariants": ["Logo 不变", "B 方向的留白、配色和字体系统不变"],
        },
        {
            "after_checkpoint": "converge",
            "message": "我隔天回来继续：保留 v2 的礼盒和淘宝主图，只把门店立牌的留白调回 v1 那个更疏的版本，别把已删的价格标签带回来。",
            "expected_changes": ["从 v1 恢复门店立牌留白参数", "继续保留 v2 的其他资产"],
            "invariants": ["礼盒不回退", "淘宝主图不回退", "价格标签保持删除"],
        },
    ],
    "DAB-L4-CAM-003": [
        {
            "after_checkpoint": "scope_change",
            "message": "小红书竖版里产品底部被裁掉了。只修 3:4 版本的安全区，天猫首图和详情页首屏已经通过，不要重新导出。",
            "expected_changes": ["修复小红书产品安全区", "仅重新导出 3:4 资产"],
            "invariants": ["胜出方向不变", "天猫首图和详情页首屏字节级冻结"],
        },
        {
            "after_checkpoint": "scope_change",
            "message": "新会话继续：再补一张 1:1 社媒图，沿用 v2 的主视觉和一句卖点；前三张不要动，也不要回到未胜出的方向。",
            "expected_changes": ["新增 1:1 社媒资产", "从 v2 继承胜出方向与批准文案"],
            "invariants": ["原三张资产保持不变", "不得使用落选方向"],
        },
    ],
    "DAB-L4-PSF-003": [
        {
            "after_checkpoint": "export",
            "message": "工厂补充：背面最小文字不得小于 6 pt。只检查并修正背面法定文案，刀模、正面和条码区都不要移动。",
            "expected_changes": ["验证背面最小字号", "仅在低于 6 pt 时调整背面法定文案"],
            "invariants": ["125×205 mm 含出血画板不变", "刀模、正面和条码区不变"],
        },
        {
            "after_checkpoint": "export",
            "message": "隔天恢复这个项目：净含量从 200 g 改成 180 g。基于 v2 只更新对应文字并重新 preflight，不要重做版式或色彩。",
            "expected_changes": ["净含量改为 180 g", "重新运行受影响页面的 preflight"],
            "invariants": ["尺寸、出血、刀模和 CMYK 设置不变", "其他批准文案不变"],
        },
    ],
    "DAB-L4-ECO-003": [
        {
            "after_checkpoint": "revise",
            "message": "结构通过，但产品陶土红偏成了橙色。只按产品源图校正产品本体颜色，暖米色背景和文字位置都别动。",
            "expected_changes": ["校正产品本体色差", "验证产品轮廓和接口未改变"],
            "invariants": ["暖米色背景不变", "首屏文字和产品位置不变"],
        },
        {
            "after_checkpoint": "revise",
            "message": "新会话继续：客户又要把第三个卖点放回首屏，但只放成底部小标签。以 v2 为底，不要恢复 v0 那套拥挤排版。",
            "expected_changes": ["新增底部第三卖点小标签", "沿用 v2 的精简层级"],
            "invariants": ["不得恢复 v0 的全部文字", "产品颜色、位置和背景不变"],
        },
    ],
    "DAB-L4-MFA-003": [
        {
            "after_checkpoint": "resume",
            "message": "邮件图尺寸临时改成 600×240。只重新排版并导出邮件版本，已完成的四个渠道和官网版本不要重跑。",
            "expected_changes": ["将邮件版本改为 600×240", "仅重导出邮件资产"],
            "invariants": ["其他渠道输出保持不变", "标题、日期和地点完整"],
        },
        {
            "after_checkpoint": "resume",
            "message": "隔天继续：Story 的报名信息被平台按钮挡住，请从 v2 只上移 Story 的报名区；邮件 600×240 和其他版本都冻结。",
            "expected_changes": ["上移 Story 报名区到安全区", "只重新导出 Story"],
            "invariants": ["邮件使用 600×240", "其余四个渠道和官网不变"],
        },
    ],
    "DAB-L4-CFR-001": [
        {
            "after_checkpoint": "edit",
            "message": "Logo 大小通过，但纸张质感还有点像滤镜。只把颗粒强度降低约 30%，标题、几何和所有活动信息都别动。",
            "expected_changes": ["背景颗粒强度降低约 30%", "生成局部差异清单"],
            "invariants": ["Logo 保持上一轮尺寸", "标题、几何、蓝橙配色和活动信息不变"],
        },
        {
            "after_checkpoint": "compare",
            "message": "隔天客户改口：Logo 不要缩小，恢复 v0 的尺寸，但改成低对比度；背景保留 v2 的细颗粒，其他已通过内容不动。",
            "expected_changes": ["仅恢复 Logo 尺寸并降低对比度", "组合 v0 Logo 尺寸与 v2 背景状态"],
            "invariants": ["背景保持 v2", "标题、几何、蓝橙配色和活动信息不变"],
        },
    ],
    "DAB-L4-CFR-003": [
        {
            "after_checkpoint": "revise",
            "message": "错字修好了。现在只交换第二、第三卖点的顺序，产品、主标题、背景和字号都保持上一版。",
            "expected_changes": ["交换第二、第三卖点顺序", "验证未发生其他布局变化"],
            "invariants": ["低噪运行拼写保持正确", "产品、主标题、背景和字号不变"],
        },
        {
            "after_checkpoint": "revise",
            "message": "新会话继续：客户要回到 v1 的卖点顺序，但保留 v2 已修正的错字和第三卖点上移位置；不要整张重生成。",
            "expected_changes": ["选择性恢复 v1 的卖点顺序", "保留 v2 的文字修正和位置参数"],
            "invariants": ["产品、主标题和背景不变", "不得重新生成整张图片"],
        },
    ],
    "DAB-L4-CFRY-002": [
        {
            "after_checkpoint": "production",
            "message": "工厂要求白墨层向外扩 0.2 mm。只更新白墨层并重新检查套准，刀线、插槽和底座尺寸都不要动。",
            "expected_changes": ["白墨层外扩 0.2 mm", "重新验证白墨与刀线套准"],
            "invariants": ["刀线、插槽和底座尺寸不变", "不增加挂孔"],
        },
        {
            "after_checkpoint": "production",
            "message": "隔天继续：底座材质从透明改成磨砂透明。基于 v2 只更新 CMF 和 mockup，生产几何、白墨层和刀线冻结。",
            "expected_changes": ["更新底座 CMF 为磨砂透明", "仅重渲染受影响 mockup"],
            "invariants": ["生产几何不变", "白墨层、刀线、插槽和公差不变"],
        },
    ],
}

EDIT_PARAMETERS = {
    "DAB-L4-BID-001": [
        ("whitespace_density", "selected_direction/layout", "enum", "sparse|balanced|dense", "compare layout token and occupied-area ratio"),
    ],
    "DAB-L4-CAM-003": [
        ("channel_scope", "campaign/export_set", "dimension_list", "append-only unless confirmed", "manifest contains only requested additions"),
        ("safe_area", "xiaohongshu_3_4/product", "number", "move within canvas", "product bounding box remains inside safe area"),
    ],
    "DAB-L4-PSF-003": [
        ("artboard_size_mm", "print_document/artboard", "dimension_list", "factory-confirmed values only", "preflight reports finished size and bleed"),
        ("legal_copy_pt", "back_panel/legal_copy", "number", ">=6 pt", "minimum text-size check"),
    ],
    "DAB-L4-ECO-003": [
        ("hero_copy_items", "hero/copy_group", "dimension_list", "brief-approved claims only", "OCR and hierarchy check"),
        ("product_color", "hero/product", "string", "match source image", "perceptual color comparison against source"),
    ],
    "DAB-L4-MFA-003": [
        ("channel_dimensions", "export_manifest", "dimension_list", "positive width and height", "decoded output dimensions equal manifest"),
        ("story_safe_area", "story/registration_group", "number", "translate only", "registration group clears platform occlusion zone"),
    ],
    "DAB-L4-CFR-001": [
        ("logo_scale_pct", "poster/logo", "number", "relative to v0", "bounding-box ratio check"),
        ("paper_grain_strength_pct", "poster/background_texture", "number", "0..100", "masked texture comparison"),
    ],
    "DAB-L4-CFR-003": [
        ("selling_point_order", "hero/selling_points", "dimension_list", "approved copy IDs only", "object order and OCR check"),
        ("selling_point_y", "hero/selling_point_3", "number", "translate only", "object-transform diff"),
    ],
    "DAB-L4-CFRY-002": [
        ("acrylic_thickness_mm", "production/material", "number", "factory-confirmed values only", "spec-to-drawing equality"),
        ("white_ink_spread_mm", "production/white_ink_layer", "number", "0..1 mm", "vector offset measurement"),
    ],
    "DAB-L3-CAM-002": [
        ("target_dimensions", "campaign/canvases", "dimension_list", "three specified sizes", "decoded dimensions equal request"),
    ],
    "DAB-L3-MFA-001": [
        ("target_formats", "campaign/export_manifest", "dimension_list", "ten specified formats", "ten unique outputs match manifest"),
    ],
    "DAB-L4-MFA-002": [
        ("target_formats", "campaign/export_manifest", "dimension_list", "seven specified formats", "seven unique outputs match manifest"),
        ("story_url_y", "story/registration_url", "number", "translate only", "URL remains in safe area"),
    ],
    "DAB-L3-CFR-002": [
        ("title_scale_pct", "poster/main_title", "number", "115% ±2% of source", "bounding-box ratio check"),
        ("event_mark_position", "poster/event_mark", "enum", "top-right safe area", "object-transform and safe-area check"),
    ],
    "DAB-L4-RTO-003": [
        ("background_texture", "detail_page/background", "enum", "original fine-clay-paper texture", "reference-similarity and region-diff check"),
    ],
}


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: row must be an object")
            rows.append(value)
    return rows


def reference_role(item: dict[str, Any]) -> tuple[str, list[str], str]:
    kind = item["kind"]
    role = item["role"].lower()
    if kind == "product_image":
        return "product_identity", ["placement", "scale", "lighting_context"], "preserve_exact"
    if kind == "brand_asset":
        return "brand_system", ["palette", "typography", "brand_tokens"], "preserve_rules"
    if kind == "candidate_set":
        return "candidate_option", ["evaluation", "selection"], "analysis_only"
    if kind == "existing_design":
        if any(token in role for token in ("approved", "master", "artwork")):
            return "approved_master", ["localized_edit", "adaptation"], "preserve_unedited_regions"
        if "ip_" in role:
            return "source_artwork", ["product_application", "mockup"], "preserve_identity"
        return "edit_target", ["localized_edit", "system_extraction"], "preserve_unedited_regions"
    if kind == "reference_image":
        if any(token in role for token in ("layout", "composition")):
            return "layout_reference", ["layout_principles", "information_rhythm"], "abstract_only"
        return "style_reference", ["visual_principles", "mood", "design_language"], "abstract_only"
    return "supporting_asset", ["task_grounding"], "preserve_exact"


def make_reference_contract(row: dict[str, Any]) -> list[dict[str, Any]]:
    optional = ZERO_SHOT_OPTIONAL_INPUTS.get(row["id"], set())
    contract: list[dict[str, Any]] = []
    for item in row["inputs"]:
        if item.get("availability") != "provided" or not item.get("asset_id"):
            continue
        role, allowed, policy = reference_role(item)
        contract.append(
            {
                "input_id": item["id"],
                "reference_role": role,
                "allowed_influence": allowed,
                "identity_policy": policy,
                "optional_for_zero_shot": item["id"] in optional,
            }
        )
    return contract


def make_context_conditions(row: dict[str, Any], contract: list[dict[str, Any]]) -> list[dict[str, Any]]:
    available = [
        item["id"] for item in row["inputs"] if item.get("availability") == "provided"
    ]
    reference_grounded = {
        "id": "reference_grounded",
        "include_input_ids": available,
        "include_preference_memory": False,
        "purpose": "Measure task performance with all task-provided references and no prior preference memory.",
    }
    if row["id"] not in CONTEXT_ABLATION_IDS:
        return [reference_grounded]

    optional = {
        item["input_id"] for item in contract if item["optional_for_zero_shot"]
    }
    zero_shot = {
        "id": "zero_shot",
        "include_input_ids": [item_id for item_id in available if item_id not in optional],
        "include_preference_memory": False,
        "query_override": ZERO_SHOT_QUERIES[row["id"]],
        "purpose": "Measure alignment from the brief and task-required source assets without optional visual references.",
    }
    personalized = {
        "id": "personalized",
        "include_input_ids": available,
        "include_preference_memory": True,
        "purpose": "Measure incremental value from project-scoped accepted and rejected preference memory.",
    }
    return [zero_shot, reference_grounded, personalized]


def make_feedback(row: dict[str, Any]) -> list[dict[str, Any]]:
    original = copy.deepcopy(row["feedback"])
    if not original:
        return []
    first = original[0]
    if row["id"] in DEEP_FIRST_CHECKPOINT:
        first["after_checkpoint"] = DEEP_FIRST_CHECKPOINT[row["id"]]
    elif row["id"] in EXPLORATION_IDS:
        first["after_checkpoint"] = "select"
    first.update(
        {
            "turn_id": "feedback-01",
            "session_id": "session-01",
            "input_version": "v0",
            "expected_version": "v1",
            "requires_confirmation": False,
        }
    )
    feedback = [first]
    for index, item in enumerate(DEEP_FOLLOWUPS.get(row["id"], []), 2):
        enriched = copy.deepcopy(item)
        enriched.update(
            {
                "turn_id": f"feedback-{index:02d}",
                "session_id": "session-01" if index == 2 else "session-02",
                "input_version": f"v{index - 1}",
                "expected_version": f"v{index}",
                "requires_confirmation": False,
            }
        )
        if index == 3:
            enriched["resume_from_version"] = "v2"
        feedback.append(enriched)
    return feedback


def make_edit_parameters(case_id: str) -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "target": target,
            "value_type": value_type,
            "allowed_change": allowed_change,
            "verification": verification,
        }
        for name, target, value_type, allowed_change, verification in EDIT_PARAMETERS.get(case_id, [])
    ]


def make_structured_artifacts(case_id: str) -> list[dict[str, Any]]:
    common = [
        {
            "name": "verification.json",
            "format": "JSON",
            "required": True,
            "validation": "Contains per-check pass/fail, evidence references, and hard-gate status.",
        },
        {
            "name": "trajectory.jsonl",
            "format": "JSONL",
            "required": True,
            "validation": "Contains observable plan, tool, artifact, checkpoint, feedback, and state-version events; no private chain of thought.",
        },
    ]
    if case_id not in STRUCTURED_EDIT_IDS:
        return common
    return [
        {
            "name": "preview.png",
            "format": "PNG",
            "required": True,
            "validation": "Decodes successfully and corresponds to the final editable document state.",
        },
        {
            "name": "design_document.json",
            "format": "JSON",
            "required": True,
            "validation": "Contains stable object IDs, layer hierarchy, transforms, styles, text, and asset bindings.",
        },
        {
            "name": "change_set.json",
            "format": "JSON",
            "required": True,
            "validation": "Lists created, updated, deleted, and unchanged object IDs against the input state.",
        },
        *common,
    ]


def make_workflow(row: dict[str, Any]) -> list[dict[str, Any]]:
    if row["id"] not in EXPLORATION_IDS:
        return copy.deepcopy(row["expected_workflow"])
    return [
        {
            "checkpoint": "understand",
            "required_outcomes": ["结构化业务目标、受众、约束与冲突", "明确参考图各自角色而非混合模仿"],
        },
        {
            "checkpoint": "diverge",
            "required_outcomes": ["生成 8–12 个低成本文字或缩略假设", "每个假设关联 brief 依据且不提前做高保真终稿"],
        },
        {
            "checkpoint": "cluster",
            "required_outcomes": ["将假设聚类为恰好 3 个 Creative Territories", "说明三个方向的设计逻辑、取舍与适配风险"],
        },
        {
            "checkpoint": "select",
            "required_outcomes": ["等待并记录人类选择与理由", "未获选择前不得静默决定最终方向"],
        },
        {
            "checkpoint": "converge",
            "required_outcomes": ["只深化被选方向", "保持已批准资产、约束与反馈状态"],
        },
        {
            "checkpoint": "deliver",
            "required_outcomes": ["完成原 brief 的中间与最终交付", "输出方向映射、验证结果与可审计 trajectory"],
        },
    ]


def make_human_checkpoints(row: dict[str, Any], feedback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if row["level"] == "L3":
        return []
    if row["id"] in EXPLORATION_IDS:
        return [
            {
                "after_checkpoint": "cluster",
                "decision_type": "select_creative_territory",
                "required": True,
                "evidence": "Selected territory ID plus a short rationale must be recorded before convergence.",
            }
        ]
    checkpoint = feedback[0]["after_checkpoint"] if feedback else row["expected_workflow"][1]["checkpoint"]
    decision_type = (
        "approve_production_parameters"
        if row["category"] == "concept_to_factory_ready"
        else "confirm_revision_or_scope"
    )
    return [
        {
            "after_checkpoint": checkpoint,
            "decision_type": decision_type,
            "required": True,
            "evidence": "Human decision, affected scope, locked invariants, and resulting state version must be recorded.",
        }
    ]


def upgrade(row: dict[str, Any]) -> dict[str, Any]:
    upgraded = copy.deepcopy(row)
    case_id = row["id"]
    upgraded["schema_version"] = "0.2"
    upgraded["revision"] = {
        "base_dataset": "briefs.v0.1.jsonl",
        "base_brief_id": case_id,
        "business_scope_changed": False,
        "protocol_changes": [
            "explicit reference and state contracts",
            "observable trajectory and verification artifacts",
            "designer-feedback capability tags",
        ],
    }
    if case_id in EXPLORATION_QUERY_REWRITES:
        upgraded["initial_query"] = EXPLORATION_QUERY_REWRITES[case_id]
        upgraded["revision"]["protocol_changes"].append("diverge-cluster-select-converge exploration protocol")

    upgraded["expected_workflow"] = make_workflow(upgraded)
    if case_id in EXPLORATION_IDS:
        first_intermediate = next(
            item for item in upgraded["deliverables"] if item["stage"] == "intermediate"
        )
        first_intermediate["count"] = 3
        first_intermediate["requirements"] = list(dict.fromkeys([
            *first_intermediate["requirements"],
            "三个 Creative Territories 可盲辨且设计逻辑不同",
        ]))
        upgraded["deliverables"].insert(
            0,
            {
                "id": "exploration-map",
                "stage": "intermediate",
                "type": "creative_hypothesis_map",
                "count": 1,
                "formats": ["JSON", "PNG"],
                "requirements": ["包含 8–12 个低成本假设", "聚类为恰好三个方向并链接到 brief 依据"],
            },
        )

    contract = make_reference_contract(upgraded)
    feedback = make_feedback(upgraded)
    upgraded["feedback"] = feedback
    upgraded["reference_contract"] = contract
    upgraded["context_conditions"] = make_context_conditions(upgraded, contract)
    upgraded["preference_memory"] = PREFERENCE_MEMORY.get(
        case_id,
        {
            "scope": "none",
            "source": "none",
            "accepted_signals": [],
            "rejected_signals": [],
        },
    )
    upgraded["project_state"] = {
        "project_id": f"project:{case_id.lower()}",
        "starting_version": "v0",
        "locked_invariants": copy.deepcopy(upgraded["constraints"]["hard"]),
        "editable_targets": [item["id"] for item in upgraded["deliverables"]],
        "resume_policy": "checkpoint_and_version" if case_id in DEEP_REVISION_IDS else "checkpoint_only",
        "preference_memory_scope": "project" if case_id in CONTEXT_ABLATION_IDS else "none",
    }
    upgraded["edit_parameters"] = make_edit_parameters(case_id)
    upgraded["structured_artifacts"] = make_structured_artifacts(case_id)
    upgraded["human_checkpoints"] = make_human_checkpoints(upgraded, feedback)

    checks = [
        "brief_adherence",
        "deliverable_completeness",
        "locked_invariants",
        "reference_role_compliance",
    ]
    if case_id in DEEP_REVISION_IDS:
        checks.extend(["state_version_continuity", "feedback_delta_only", "resume_integrity"])
    if case_id in EXPLORATION_IDS:
        checks.extend(["territory_distinctness", "human_selection_used"])
    if case_id in STRUCTURED_EDIT_IDS:
        checks.extend(["object_graph_validity", "change_set_scope"])
    upgraded["verification_contract"] = {
        "checks": checks,
        "evidence_required": True,
        "failure_policy": "block_delivery_on_hard_gate",
    }

    tags = ["tool_execution" if row["level"] == "L3" else "workflow_orchestration"]
    if len(contract) >= 2:
        tags.append("multi_reference_binding")
    if case_id in DEEP_REVISION_IDS:
        tags.extend(["multi_turn_revision", "state_recovery"])
    if case_id in EXPLORATION_IDS:
        tags.append("creative_exploration")
    if case_id in STRUCTURED_EDIT_IDS:
        tags.append("structured_editing")
        upgraded["constraints"]["hard"].append(
            "除最终预览外，必须输出可编辑对象图、对象级 change set 和可机读验证结果。"
        )
        for tool in ("design_object_inspector", "layer_graph_editor", "change_set_exporter"):
            if tool not in upgraded["tools_available"]:
                upgraded["tools_available"].append(tool)
    if case_id in CONTEXT_ABLATION_IDS:
        tags.append("context_ablation")
    if row["category"] == "concept_to_factory_ready":
        tags.append("production_execution")
    upgraded["capability_tags"] = tags
    return upgraded


def build(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [upgrade(row) for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    rows = build(load_rows(args.input))
    rendered = "\n".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows
    ) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {len(rows)} v0.2 episode rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
