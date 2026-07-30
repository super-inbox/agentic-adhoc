"use strict";

const fs = require("fs");
const path = require("path");
const {
  hashObject,
  loadJson,
  normalizeQuery,
  resolveRoot,
  sha256,
  slug,
  writeJson,
  writeJsonl,
} = require("./common.cjs");
const { makeRecord } = require("./schema.cjs");

const FIXED_TIME = "2026-07-29T00:00:00.000Z";

const GAP_CONCEPTS = [
  {
    en: "official passport photo from a text description",
    zh: "只用文字生成官方护照证件照",
    subject: "identity portrait",
  },
  {
    en: "visa application headshot with exact biometric dimensions",
    zh: "符合生物识别尺寸的签证头像",
    subject: "identity portrait",
  },
  {
    en: "one-page software engineer resume",
    zh: "软件工程师单页简历",
    subject: "resume document",
  },
  {
    en: "mobile banking app wireframe",
    zh: "手机银行 App 线框图",
    subject: "interface design",
  },
  {
    en: "live analytics dashboard UI mockup",
    zh: "实时数据看板 UI 原型",
    subject: "interface design",
  },
  {
    en: "wedding reception seating chart with table assignments",
    zh: "带桌号分配的婚宴座位表",
    subject: "event stationery",
  },
  {
    en: "concert ticket with a working QR code",
    zh: "带可扫描二维码的演唱会门票",
    subject: "functional ticket",
  },
  {
    en: "fine-line botanical tattoo stencil",
    zh: "植物细线纹身转印稿",
    subject: "tattoo design",
  },
  {
    en: "measured apartment floor plan",
    zh: "带精确尺寸的公寓平面图",
    subject: "architectural drawing",
  },
  {
    en: "printable sewing pattern for a fitted jacket",
    zh: "合身夹克的可打印缝纫纸样",
    subject: "sewing pattern",
  },
  {
    en: "restaurant menu with item prices and allergen codes",
    zh: "含价格和过敏原编码的餐厅菜单",
    subject: "functional menu",
  },
  {
    en: "full-wrap novel book cover with spine measurements",
    zh: "含书脊尺寸的小说全封套",
    subject: "publication cover",
  },
  {
    en: "podcast cover artwork sized for streaming platforms",
    zh: "播客平台尺寸的节目封面",
    subject: "audio cover",
  },
  {
    en: "music album cover with a track list on the back",
    zh: "背面带曲目的音乐专辑封面",
    subject: "audio cover",
  },
  {
    en: "company org chart with reporting lines",
    zh: "带汇报关系的公司组织架构图",
    subject: "business diagram",
  },
  {
    en: "accurate scatter plot generated from my CSV columns",
    zh: "根据 CSV 列精确绘制散点图",
    subject: "data visualization",
  },
  {
    en: "editable investor pitch-deck slide master",
    zh: "可编辑的投资人路演幻灯片母版",
    subject: "presentation design",
  },
  {
    en: "knitting pattern chart with stitch counts",
    zh: "带针数的编织图解",
    subject: "craft pattern",
  },
  {
    en: "animated logo sting with transparent video output",
    zh: "透明背景的视频 Logo 动效",
    subject: "motion design",
  },
  {
    en: "3D-printable STL model of a replacement gear",
    zh: "可 3D 打印的替换齿轮 STL 模型",
    subject: "3D model",
  },
];

const GAP_ARTIFACTS = {
  en: [
    "Please create {concept}.",
    "Can this tool make {concept} for me?",
    "I need {concept}, clean and production-ready.",
    "pls do {concept} asap",
  ],
  zh: [
    "请帮我做{concept}。",
    "这个工具能生成{concept}吗？",
    "我需要{concept}，要能直接使用。",
    "急，帮做个{concept}",
  ],
  mixed: [
    "帮我做 {concept_en}，要 production-ready。",
    "Need {concept_en}，可以直接生成吗？",
    "{concept_zh} pls，尺寸要准确。",
    "想要 {concept_en}，中文内容也可以。",
  ],
};

const BOUNDARY_SCENARIOS = {
  "template-english-grammar-wordlist-infographic::template-vocabulary": {
    en: "English-Chinese learning cards for sound-alike words, with paired meanings",
    zh: "中英双语同音词学习卡，带词义对照",
  },
  "template-species-science::template-vocabulary": {
    en: "a bilingual ginkgo field guide combining names and species facts",
    zh: "结合双语名称和物种知识的银杏图鉴",
  },
  "template-education-card::template-english-grammar-wordlist-infographic": {
    en: "a kid-friendly cartoon explainer about confusing English homophones",
    zh: "儿童友好的英语易混同音词卡通知识图",
  },
  "template-interior-design-mood-board-generator::template-lifestyle-watercolor-infographic": {
    en: "cozy reading-nook inspiration with a room palette and gentle reading rituals",
    zh: "同时包含空间配色和阅读仪式的治愈阅读角灵感",
  },
  "template-interior-design-mood-board-generator::template-product-poster": {
    en: "an aromatherapy corner visual featuring both the room palette and diffuser benefits",
    zh: "同时突出空间配色和香薰机卖点的疗愈角视觉",
  },
  "template-interior-design-mood-board-generator::template-species-science": {
    en: "a ginkgo-themed bedroom visual with decor materials and botanical facts",
    zh: "兼顾软装材质和银杏科普的植物主题卧室视觉",
  },
  "template-education-card::template-species-science": {
    en: "a child-friendly ginkgo science card with key facts and species details",
    zh: "面向儿童、包含关键知识和物种细节的银杏科普卡",
  },
  "template-fandom-character-grid-poster::template-mbti-generic": {
    en: "a Marvel cast grid that groups heroes by personality",
    zh: "按人格分组的漫威角色阵容图",
  },
  "template-fandom-character-grid-poster::template-figure-principles-infographic": {
    en: "a historical-character poster about legendary samurai and their guiding principles",
    zh: "展示传奇武士及其人生信条的历史人物海报",
  },
  "template-lifestyle-watercolor-infographic::template-product-poster": {
    en: "a cozy tea-routine visual centered on an electric kettle and its benefits",
    zh: "围绕电热水壶和使用益处展开的治愈饮茶视觉",
  },
  "template-lifestyle-watercolor-infographic::template-species-science": {
    en: "a watercolor ginkgo visual mixing botanical facts with calm nature habits",
    zh: "融合银杏科普和自然疗愈习惯的水彩视觉",
  },
  "template-intangible-heritage::template-travel": {
    en: "a visual guide to paper-cutting culture made for travelers visiting Shaanxi",
    zh: "给陕西旅行者看的剪纸文化视觉指南",
  },
  "template-education-card::template-intangible-heritage": {
    en: "a kid-friendly knowledge card explaining paper-cutting history and process",
    zh: "面向儿童讲解剪纸历史与工序的知识卡",
  },
  "template-product-poster::template-recipe": {
    en: "a portable-blender smoothie visual showing product benefits and recipe steps",
    zh: "同时展示便携榨汁杯卖点和果昔步骤的视觉",
  },
  "template-recipe::template-vocabulary": {
    en: "a bilingual Cuban-sandwich visual with ingredient names and preparation steps",
    zh: "含双语食材名称和制作步骤的古巴三明治视觉",
  },
  "template-mbti-generic::template-mbti-personality-compatibility-infographic": {
    en: "an INFJ and ENTP personality chart whose focus could be behavior or relationship fit",
    zh: "可侧重行为对比或关系适配的 INFJ 与 ENTP 人格图",
  },
  "template-figure-principles-infographic::template-mbti-generic": {
    en: "an Einstein character chart connecting personality traits with life principles",
    zh: "把性格特质和人生原则联系起来的爱因斯坦人物图",
  },
  "template-fandom-character-grid-poster::template-mbti-personality-compatibility-infographic": {
    en: "INFJ and ENTP represented as Chiikawa characters in a relationship-focused cast visual",
    zh: "用吉伊卡哇角色表现 INFJ 与 ENTP 关系的角色视觉",
  },
};

function minorTypo(text) {
  const match = [...text.matchAll(/[A-Za-z]{6,}/g)][0];
  if (!match) return `${text} 哈`;
  const word = match[0];
  const index = match.index + Math.max(1, Math.floor(word.length / 2));
  return `${text.slice(0, index)}${text.slice(index + 1)}`;
}

function withIndefiniteArticle(phrase) {
  const trimmed = phrase.trim();
  const article = /^(?:[aeiou]|ESL\b|MBTI\b|A3\b)/i.test(trimmed)
    ? "an"
    : "a";
  return `${article} ${trimmed}`;
}

function renderCoreQuery(entry, concept, language, difficulty, variant) {
  const enArtifact =
    entry.generation_profile.artifacts_en[
      variant % entry.generation_profile.artifacts_en.length
    ];
  const zhArtifact =
    entry.generation_profile.artifacts_zh[
      variant % entry.generation_profile.artifacts_zh.length
    ];
  if (language === "en") {
    if (difficulty === "low") {
      return `Create ${withIndefiniteArticle(enArtifact)} for ${concept.en}.`;
    }
    if (difficulty === "medium") {
      return `Could you make ${concept.en} into ${withIndefiniteArticle(enArtifact)} for a beginner audience, with a calm editorial look in 4:5?`;
    }
    const query = `${concept.en} — make the subject, key details, and visual organization instantly scannable; informal tone, 4:5 pls`;
    return variant % 2 ? minorTypo(query) : query;
  }
  if (language === "zh") {
    if (difficulty === "low") {
      return `请制作一张${concept.zh}的${zhArtifact}。`;
    }
    if (difficulty === "medium") {
      return `能不能把${concept.zh}做成${zhArtifact}？给初学者看，风格清爽，竖版 4:5。`;
    }
    return `${concept.zh}，想做成一眼能看懂的竖版视觉，给新手看，别太学术哈`;
  }
  if (difficulty === "low") {
    return `帮我做一个 ${concept.en} 的${zhArtifact}，labels 清楚一点。`;
  }
  if (difficulty === "medium") {
    return `${concept.zh} 做成 ${withIndefiniteArticle(enArtifact)}，for beginners，4:5 竖版。`;
  }
  return `Need ${concept.en}，信息要一眼扫懂但别做成 generic poster，竖版 pls`;
}

function coreTransformations(language, difficulty, variant) {
  if (difficulty === "low") {
    return ["different_example", "explicit_artifact"];
  }
  if (difficulty === "medium") {
    return [
      "paraphrase",
      "conversational",
      "audience_modifier",
      variant % 2 ? "aspect_ratio_modifier" : "style_modifier",
    ];
  }
  return [
    "implicit_intent",
    language === "mixed" ? "code_switch" : "underspecified",
    variant % 2 ? "typo_noise" : "layout_modifier",
    "boundary_nearby",
  ];
}

function languageFor(conceptIndex, variant) {
  const cycle = ["zh", "en", "zh", "en", "mixed"];
  return cycle[(conceptIndex + variant * 2) % cycle.length];
}

function generateCore({ seeds, registry, countPerTarget, randomSeed }) {
  const byTarget = new Map(
    seeds
      .filter((seed) => seed.gold_targets.length === 1)
      .map((seed) => [seed.gold_targets[0], seed]),
  );
  const records = [];
  for (const entry of registry.templates) {
    const seed = byTarget.get(entry.canonical_id);
    if (!seed) continue;
    const concepts = entry.generation_profile?.concepts ?? [];
    if (!concepts.length) {
      throw new Error(`${entry.canonical_id} has no generation concepts`);
    }
    for (let index = 0; index < countPerTarget; index += 1) {
      const conceptIndex = index % concepts.length;
      const variant = Math.floor(index / concepts.length);
      const language = languageFor(conceptIndex, variant);
      const difficulty = ["low", "medium", "high"][variant % 3];
      const query = renderCoreQuery(
        entry,
        concepts[conceptIndex],
        language,
        difficulty,
        index,
      );
      records.push(
        makeRecord({
          id: `vir-v2-core-${seed.seed_id}-${String(index + 1).padStart(2, "0")}`,
          seed,
          clusterId: `vir-v2-${seed.seed_id}-cluster-${String(
            conceptIndex + 1,
          ).padStart(2, "0")}`,
          partition: "core",
          query,
          language,
          difficulty,
          transformations: coreTransformations(
            language,
            difficulty,
            index,
          ),
          ontology: entry.ontology,
          gold: {
            target_mode: "single",
            targets: [entry.canonical_id],
            acceptable_target_sets: [],
            must_abstain: false,
          },
          randomSeed,
          generatedAt: FIXED_TIME,
        }),
      );
    }
  }
  return records;
}

function generateContentGap({ seed, count, randomSeed }) {
  const records = [];
  for (let index = 0; index < count; index += 1) {
    const conceptIndex = index % GAP_CONCEPTS.length;
    const variant = Math.floor(index / GAP_CONCEPTS.length);
    const concept = GAP_CONCEPTS[conceptIndex];
    const language = ["zh", "en", "mixed", "en"][variant % 4];
    const difficulty = ["low", "medium", "high", "high"][variant % 4];
    const patterns = GAP_ARTIFACTS[language];
    let query = patterns[variant % patterns.length]
      .replace("{concept}", language === "zh" ? concept.zh : concept.en)
      .replace("{concept_en}", concept.en)
      .replace("{concept_zh}", concept.zh);
    if (difficulty === "high" && variant % 2) query = minorTypo(query);
    records.push(
      makeRecord({
        id: `vir-v2-gap-${String(index + 1).padStart(3, "0")}`,
        seed,
        clusterId: `vir-v2-gap-cluster-${String(conceptIndex + 1).padStart(
          2,
          "0",
        )}`,
        partition: "content_gap",
        query,
        language,
        difficulty,
        transformations: [
          variant === 0 ? "explicit_artifact" : "paraphrase",
          variant === 1 ? "conversational" : "different_example",
          language === "mixed" ? "code_switch" : "unsupported_visual_request",
          difficulty === "high" ? "noisy" : "clean",
        ],
        ontology: {
          subject_event: concept.subject,
          information_type: "unsupported visual production request",
          style_layout: "requested artifact-specific layout",
        },
        gold: {
          target_mode: "none",
          targets: [],
          acceptable_target_sets: [],
          must_abstain: true,
          scope_note:
            conceptIndex < 2
              ? "Text-only generation scope; portrait-upload workflows excluded."
              : null,
        },
        randomSeed,
        generatedAt: FIXED_TIME,
      }),
    );
  }
  return records;
}

function pairConcept(entry, index) {
  const concepts = entry.generation_profile.concepts;
  return concepts[index % concepts.length];
}

function challengeLanguage(index) {
  return ["zh", "en", "mixed"][index % 3];
}

function challengeVariantSuffix(language, variation) {
  const suffixes = {
    en: [
      "",
      " Keep it concise for teens.",
      " Use a vertical 4:5 layout.",
      " Give it an informal but informative social-media tone.",
    ],
    zh: [
      "",
      " 给青少年看，内容精简。",
      " 用竖版 4:5 排版。",
      " 语气轻松但信息要靠谱。",
    ],
    mixed: [
      "",
      " for teens，内容简洁一点。",
      " 用 vertical 4:5 layout。",
      " social-friendly 但信息要靠谱。",
    ],
  };
  return suffixes[language][variation % suffixes[language].length];
}

function renderAmbiguous(a, b, index, language, variation = 0) {
  const pairKey = [a.canonical_id, b.canonical_id].sort().join("::");
  const scenario = BOUNDARY_SCENARIOS[pairKey] ?? {
    en: `${pairConcept(a, index).en} with ${pairConcept(b, index + 3).en}`,
    zh: `${pairConcept(a, index).zh}与${pairConcept(b, index + 3).zh}`,
  };
  const aa = a.generation_profile.artifacts_en[index % 3];
  const ba = b.generation_profile.artifacts_en[(index + 1) % 3];
  if (language === "zh") {
    return `想做${scenario.zh}，可以偏${a.generation_profile.artifacts_zh[0]}，也可以按${b.generation_profile.artifacts_zh[0]}来呈现，重点还没定。${challengeVariantSuffix(language, variation)}`.trim();
  }
  if (language === "mixed") {
    return `${scenario.zh} / ${scenario.en}，could be ${withIndefiniteArticle(aa)} or ${withIndefiniteArticle(ba)}，重点未定 pls。${challengeVariantSuffix(language, variation)}`.trim();
  }
  return `Make ${scenario.en}; either ${withIndefiniteArticle(aa)} or ${withIndefiniteArticle(ba)} could fit because the emphasis is not settled.${challengeVariantSuffix(language, variation)}`.trim();
}

function renderMulti(
  a,
  b,
  index,
  language,
  plusUnsupported,
  variation = 0,
) {
  const ac = pairConcept(a, index);
  const bc = pairConcept(b, index + 5);
  const aa = a.generation_profile.artifacts_en[index % 3];
  const ba = b.generation_profile.artifacts_en[(index + 1) % 3];
  if (plusUnsupported) {
    if (language === "zh") {
      return `先做${ac.zh}的${a.generation_profile.artifacts_zh[0]}，再配一张符合护照标准的本人证件照。${challengeVariantSuffix(language, variation)}`.trim();
    }
    if (language === "mixed") {
      return `先做 ${ac.en} 的${a.generation_profile.artifacts_zh[0]}，plus a biometric passport photo of me。${challengeVariantSuffix(language, variation)}`.trim();
    }
    return `Create ${withIndefiniteArticle(aa)} for ${ac.en}, plus a biometric passport photo of me.${challengeVariantSuffix(language, variation)}`.trim();
  }
  if (language === "zh") {
    return `做一套两张配套视觉：第一张是${ac.zh}的${a.generation_profile.artifacts_zh[0]}，第二张是${bc.zh}的${b.generation_profile.artifacts_zh[0]}。${challengeVariantSuffix(language, variation)}`.trim();
  }
  if (language === "mixed") {
    return `做 two coordinated visuals：${withIndefiniteArticle(aa)} for ${ac.en}，再做 ${withIndefiniteArticle(ba)} for ${bc.en}。${challengeVariantSuffix(language, variation)}`.trim();
  }
  return `Create two coordinated visuals: ${withIndefiniteArticle(aa)} for ${ac.en}, and ${withIndefiniteArticle(ba)} for ${bc.en}.${challengeVariantSuffix(language, variation)}`.trim();
}

function generateChallenges({
  registry,
  ambiguousCount,
  multiCount,
  randomSeed,
}) {
  const pairs = registry.boundaryPairs();
  if (!pairs.length) throw new Error("Registry has no boundary pairs");
  const ambiguousOccurrences = new Map();
  const ambiguous = [];
  for (let index = 0; index < ambiguousCount; index += 1) {
    const pair = pairs[index % pairs.length];
    const pairKey = pair.join("::");
    const variation = ambiguousOccurrences.get(pairKey) ?? 0;
    ambiguousOccurrences.set(pairKey, variation + 1);
    const a = registry.get(pair[0]);
    const b = registry.get(pair[1]);
    const language = challengeLanguage(index);
    const challengeType =
      language === "mixed"
        ? "mixed_language_noisy"
        : ["ambiguous", "boundary", "conflicting_style_information"][
            Math.floor(index / 3) % 3
          ];
    ambiguous.push(
      makeRecord({
        id: `vir-v2-challenge-amb-${String(index + 1).padStart(3, "0")}`,
        seed: null,
        clusterId: `vir-v2-boundary-${slug(pair.join("-"))}`,
        partition: "challenge",
        challengeType,
        query: renderAmbiguous(a, b, index, language, variation),
        language,
        difficulty: "high",
        transformations: [
          "boundary_case",
          "ambiguous_intent",
          language === "mixed" ? "code_switch" : "conflicting_modifier",
        ],
        ontology: {
          subject_event: `${a.ontology.subject_event} | ${b.ontology.subject_event}`,
          information_type: `${a.ontology.information_type} | ${b.ontology.information_type}`,
          style_layout: `${a.ontology.style_layout} | ${b.ontology.style_layout}`,
        },
        gold: {
          target_mode: "ambiguous",
          targets: pair,
          acceptable_target_sets: [[pair[0]], [pair[1]]],
          must_abstain: false,
        },
        randomSeed,
        generatedAt: FIXED_TIME,
      }),
    );
  }
  const multiOccurrences = new Map();
  const multi = [];
  for (let index = 0; index < multiCount; index += 1) {
    const pair = pairs[(index * 5) % pairs.length];
    const pairKey = pair.join("::");
    const variation = multiOccurrences.get(pairKey) ?? 0;
    multiOccurrences.set(pairKey, variation + 1);
    const a = registry.get(pair[0]);
    const b = registry.get(pair[1]);
    const language = challengeLanguage(index + 1);
    const plusUnsupported = index % 5 === 4;
    multi.push(
      makeRecord({
        id: `vir-v2-challenge-multi-${String(index + 1).padStart(3, "0")}`,
        seed: null,
        clusterId: `vir-v2-multi-${slug(pair.join("-"))}`,
        partition: "challenge",
        challengeType: plusUnsupported
          ? "supported_plus_unsupported"
          : "multi_intent",
        query: renderMulti(
          a,
          b,
          index,
          language,
          plusUnsupported,
          variation,
        ),
        language,
        difficulty: index % 3 === 0 ? "medium" : "high",
        transformations: [
          "multi_intent",
          language === "mixed" ? "code_switch" : "multi_clause",
          plusUnsupported ? "supported_plus_unsupported" : "paired_artifacts",
        ],
        ontology: {
          subject_event: plusUnsupported
            ? `${a.ontology.subject_event} + identity portrait`
            : `${a.ontology.subject_event} + ${b.ontology.subject_event}`,
          information_type: plusUnsupported
            ? `${a.ontology.information_type} + unsupported portrait creation`
            : `${a.ontology.information_type} + ${b.ontology.information_type}`,
          style_layout: plusUnsupported
            ? `${a.ontology.style_layout} + official photo`
            : `${a.ontology.style_layout} + ${b.ontology.style_layout}`,
        },
        gold: {
          target_mode: "multi",
          targets: plusUnsupported ? [pair[0]] : pair,
          acceptable_target_sets: [],
          must_abstain: false,
          unsupported_components: plusUnsupported
            ? ["biometric passport or ID photo requiring a person image"]
            : [],
        },
        randomSeed,
        generatedAt: FIXED_TIME,
      }),
    );
  }
  return [...ambiguous, ...multi];
}

function loadCachedResponse(cachePath, promptHash) {
  const absolute = resolveRoot(cachePath);
  if (!fs.existsSync(absolute)) return null;
  const cached = JSON.parse(fs.readFileSync(absolute, "utf8"));
  if (cached.prompt_hash !== promptHash) return null;
  return cached;
}

function buildLlmTasks({ seeds, registry, expansion }) {
  const tasks = [];
  const batchSize = Math.max(1, expansion.batch_size);
  const seedByTarget = new Map(
    seeds
      .filter((seed) => seed.gold_targets.length === 1)
      .map((seed) => [seed.gold_targets[0], seed]),
  );
  for (const entry of registry.templates) {
    for (
      let offset = 0;
      offset < expansion.core_per_target;
      offset += batchSize
    ) {
      tasks.push({
        key: `core-${entry.canonical_id}-${offset}`,
        partition: "core",
        challenge_type: null,
        count: Math.min(batchSize, expansion.core_per_target - offset),
        targets: [entry.canonical_id],
        seed: seedByTarget.get(entry.canonical_id),
        capabilities: [entry],
      });
    }
  }
  const gapSeed = seeds.find((seed) => seed.expected_abstention);
  for (let offset = 0; offset < expansion.content_gap; offset += batchSize) {
    tasks.push({
      key: `content-gap-${offset}`,
      partition: "content_gap",
      challenge_type: null,
      count: Math.min(batchSize, expansion.content_gap - offset),
      targets: [],
      seed: gapSeed,
      capabilities: [],
    });
  }
  const pairs = registry.boundaryPairs();
  for (const [kind, count] of [
    ["ambiguous", expansion.ambiguous],
    ["multi_intent", expansion.multi_intent],
  ]) {
    for (let offset = 0; offset < count; offset += batchSize) {
      const pair = pairs[Math.floor(offset / batchSize) % pairs.length];
      tasks.push({
        key: `${kind}-${offset}-${pair.join("-")}`,
        partition: "challenge",
        challenge_type: kind,
        count: Math.min(batchSize, count - offset),
        targets: pair,
        seed: null,
        capabilities: pair.map((target) => registry.get(target)),
      });
    }
  }
  return tasks;
}

function importLlmTaskRecords({
  task,
  rawRecords,
  registry,
  randomSeed,
  model,
  promptVersion,
  promptHash,
  cachePath,
  startIndex,
}) {
  const output = [];
  for (let index = 0; index < rawRecords.length; index += 1) {
    const raw = rawRecords[index];
    if (
      !raw ||
      typeof raw.query !== "string" ||
      !["zh", "en", "mixed"].includes(raw.language) ||
      !["low", "medium", "high"].includes(raw.difficulty) ||
      !Array.isArray(raw.transformation_types)
    ) {
      continue;
    }
    const ontology =
      raw.ontology &&
      ["subject_event", "information_type", "style_layout"].every(
        (key) => typeof raw.ontology[key] === "string" && raw.ontology[key],
      )
        ? raw.ontology
        : task.capabilities.length === 1
          ? task.capabilities[0].ontology
          : {
              subject_event: task.capabilities
                .map((entry) => entry.ontology.subject_event)
                .join(" + "),
              information_type: task.capabilities
                .map((entry) => entry.ontology.information_type)
                .join(" + "),
              style_layout: task.capabilities
                .map((entry) => entry.ontology.style_layout)
                .join(" + "),
            };
    const canonicalTargets = task.targets.map((target) => {
      const canonical = registry.canonicalize(target);
      if (!canonical) throw new Error(`LLM task has invalid target ${target}`);
      return canonical;
    });
    const mode =
      task.partition === "content_gap"
        ? "none"
        : task.challenge_type === "ambiguous"
          ? "ambiguous"
          : task.challenge_type === "multi_intent"
            ? "multi"
            : "single";
    const record = makeRecord({
      id: `vir-v2-llm-${String(startIndex + index + 1).padStart(4, "0")}-${sha256(raw.query).slice(0, 8)}`,
      seed: task.seed,
      clusterId:
        raw.semantic_cluster_hint ||
        `vir-v2-llm-${task.key}-${index + 1}`,
      partition: task.partition,
      challengeType:
        task.partition === "challenge" ? task.challenge_type : null,
      query: raw.query.trim(),
      language: raw.language,
      difficulty: raw.difficulty,
      transformations: raw.transformation_types,
      ontology,
      gold: {
        target_mode: mode,
        targets: canonicalTargets,
        acceptable_target_sets:
          mode === "ambiguous"
            ? canonicalTargets.map((target) => [target])
            : [],
        must_abstain: mode === "none",
        unsupported_components: raw.unsupported_components ?? [],
      },
      randomSeed,
      generationMethod: "llm",
      promptVersion,
      generatedAt: FIXED_TIME,
    });
    record.provenance.generator_model = model;
    record.provenance.generator_prompt_hash = promptHash;
    record.provenance.generator_response_cache = cachePath;
    output.push(record);
  }
  return output;
}

async function callLlmJson({
  prompt,
  model,
  temperature,
  seed,
  maxRetries,
  cachePath,
}) {
  const promptHash = sha256(prompt);
  const cached = loadCachedResponse(cachePath, promptHash);
  if (cached) return cached;
  if (!process.env.OPENAI_API_KEY) {
    throw new Error(
      "OPENAI_API_KEY is required for --provider=llm; rule expansion needs no key",
    );
  }
  const OpenAI = require("openai");
  const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  let lastError;
  for (let attempt = 1; attempt <= maxRetries; attempt += 1) {
    try {
      const response = await client.chat.completions.create({
        model,
        temperature,
        seed,
        response_format: { type: "json_object" },
        messages: [
          { role: "system", content: prompt },
          { role: "user", content: "Generate the requested JSON records." },
        ],
      });
      const raw = response.choices?.[0]?.message?.content ?? "";
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed.records)) {
        throw new Error("LLM JSON must contain records[]");
      }
      const result = {
        prompt_hash: promptHash,
        model,
        raw_output: raw,
        parsed,
        attempts: attempt,
      };
      writeJson(cachePath, result);
      return result;
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError;
}

async function expandDataset({
  config,
  seeds,
  registry,
  provider,
  dryRun = false,
  resume = true,
  quotas = {},
}) {
  const expansion = {
    ...config.expansion,
    ...quotas,
    provider: provider ?? config.expansion.provider,
  };
  if (expansion.provider === "llm") {
    const basePrompt = fs.readFileSync(
      resolveRoot("benchmarks/vir_v2/prompts/query_expander.md"),
      "utf8",
    );
    const tasks = buildLlmTasks({ seeds, registry, expansion });
    if (dryRun) {
      return {
        core: [],
        contentGap: [],
        challenge: [],
        summary: {
          requested: {
            core: 15 * expansion.core_per_target,
            content_gap: expansion.content_gap,
            ambiguous: expansion.ambiguous,
            multi_intent: expansion.multi_intent,
            total:
              15 * expansion.core_per_target +
              expansion.content_gap +
              expansion.ambiguous +
              expansion.multi_intent,
          },
          generated: { core: 0, content_gap: 0, challenge: 0, total: 0 },
          provider: "llm",
          dry_run: true,
          task_count: tasks.length,
          batch_size: expansion.batch_size,
        },
      };
    }
    const imported = [];
    for (const task of tasks) {
      const taskPrompt = `${basePrompt}

Generate exactly ${task.count} records for this task.
Task: ${JSON.stringify({
        partition: task.partition,
        challenge_type: task.challenge_type,
        targets: task.targets,
        source_seed_id: task.seed?.seed_id ?? null,
        language_distribution: expansion.languages,
        difficulty_distribution: expansion.difficulties,
      })}
Capability evidence: ${JSON.stringify(task.capabilities)}
For content_gap, verify against the supplied full registry and return only plausible unsupported visual requests.
Return {"records":[...]} and include query, language, difficulty, transformation_types, semantic_cluster_hint, ontology, and unsupported_components when relevant.`;
      const promptHash = sha256(taskPrompt);
      const cachePath = path.join(
        config.paths.cache_dir,
        `expansion-${slug(task.key)}-${promptHash.slice(0, 12)}.json`,
      );
      const result = await callLlmJson({
        prompt: taskPrompt,
        model: expansion.model,
        temperature: expansion.temperature,
        seed: config.random_seed,
        maxRetries: expansion.max_retries,
        cachePath,
      });
      imported.push(
        ...importLlmTaskRecords({
          task,
          rawRecords: result.parsed.records.slice(0, task.count),
          registry,
          randomSeed: config.random_seed,
          model: expansion.model,
          promptVersion: expansion.prompt_version,
          promptHash,
          cachePath,
          startIndex: imported.length,
        }),
      );
    }
    const core = imported.filter((record) => record.partition === "core");
    const contentGap = imported.filter(
      (record) => record.partition === "content_gap",
    );
    const challenge = imported.filter(
      (record) => record.partition === "challenge",
    );
    const summary = {
      requested: {
        core: 15 * expansion.core_per_target,
        content_gap: expansion.content_gap,
        ambiguous: expansion.ambiguous,
        multi_intent: expansion.multi_intent,
        total:
          15 * expansion.core_per_target +
          expansion.content_gap +
          expansion.ambiguous +
          expansion.multi_intent,
      },
      generated: {
        core: core.length,
        content_gap: contentGap.length,
        challenge: challenge.length,
        total: imported.length,
      },
      provider: "llm",
      random_seed: config.random_seed,
      task_count: tasks.length,
      batch_size: expansion.batch_size,
      dry_run: false,
    };
    writeJsonl(path.join(config.paths.candidate_dir, "core.jsonl"), core);
    writeJsonl(
      path.join(config.paths.candidate_dir, "content_gap.jsonl"),
      contentGap,
    );
    writeJsonl(
      path.join(config.paths.candidate_dir, "challenge.jsonl"),
      challenge,
    );
    writeJson(
      path.join(config.paths.manifest_dir, "expansion_summary.json"),
      summary,
    );
    return { core, contentGap, challenge, summary };
  }
  const positive = generateCore({
    seeds,
    registry,
    countPerTarget: expansion.core_per_target,
    randomSeed: config.random_seed,
  });
  const gapSeed = seeds.find((seed) => seed.expected_abstention);
  const contentGap = generateContentGap({
    seed: gapSeed,
    count: expansion.content_gap,
    randomSeed: config.random_seed,
  });
  const challenge = generateChallenges({
    registry,
    ambiguousCount: expansion.ambiguous,
    multiCount: expansion.multi_intent,
    randomSeed: config.random_seed,
  });
  const summary = {
    requested: {
      core: 15 * expansion.core_per_target,
      content_gap: expansion.content_gap,
      ambiguous: expansion.ambiguous,
      multi_intent: expansion.multi_intent,
      total:
        15 * expansion.core_per_target +
        expansion.content_gap +
        expansion.ambiguous +
        expansion.multi_intent,
    },
    generated: {
      core: positive.length,
      content_gap: contentGap.length,
      challenge: challenge.length,
      total: positive.length + contentGap.length + challenge.length,
    },
    provider: "rule",
    random_seed: config.random_seed,
    dry_run: dryRun,
  };
  if (!dryRun) {
    writeJsonl(path.join(config.paths.candidate_dir, "core.jsonl"), positive);
    writeJsonl(
      path.join(config.paths.candidate_dir, "content_gap.jsonl"),
      contentGap,
    );
    writeJsonl(
      path.join(config.paths.candidate_dir, "challenge.jsonl"),
      challenge,
    );
    writeJson(
      path.join(config.paths.manifest_dir, "expansion_summary.json"),
      summary,
    );
  }
  return { core: positive, contentGap, challenge, summary };
}

module.exports = {
  FIXED_TIME,
  BOUNDARY_SCENARIOS,
  GAP_CONCEPTS,
  callLlmJson,
  buildLlmTasks,
  expandDataset,
  generateChallenges,
  generateContentGap,
  generateCore,
  importLlmTaskRecords,
  loadCachedResponse,
  renderCoreQuery,
  challengeVariantSuffix,
  withIndefiniteArticle,
};
