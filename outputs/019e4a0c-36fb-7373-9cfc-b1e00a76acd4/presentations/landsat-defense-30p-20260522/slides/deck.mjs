import fsSync from "node:fs";
import path from "node:path";

const C = {
  navy: "#0F3E68",
  navy2: "#163F63",
  blue: "#2F75B5",
  cyan: "#2FB7C7",
  green: "#6EA84F",
  gold: "#C7892B",
  orange: "#D97A1D",
  paper: "#F6F8FB",
  white: "#FFFFFF",
  text: "#22384D",
  muted: "#6D7F92",
  line: "#D7E2ED",
  line2: "#9DBBDD",
  paleBlue: "#EEF5FC",
  paleCyan: "#EFFBFC",
  paleGreen: "#F1F8ED",
  paleGold: "#FFF7E8",
  dark: "#112E4B",
};

const FONT = "Microsoft YaHei";
const FONT_MONO = "Aptos Mono";
const W = 1280;
const H = 720;

function repoRoot(ctx) {
  return path.resolve(ctx.workspaceDir, "..", "..", "..", "..");
}

function asset(ctx, ...parts) {
  return path.join(repoRoot(ctx), ...parts);
}

function exists(filePath) {
  return Boolean(filePath) && fsSync.existsSync(filePath);
}

function line(color, width = 1) {
  return { color, width, transparency: 0 };
}

function shape(slide, ctx, options) {
  return ctx.addShape(slide, options);
}

function text(slide, ctx, options) {
  const {
    left,
    top,
    width,
    height,
    content,
    size = 18,
    color = C.text,
    bold = false,
    align = "left",
    valign = "top",
    face = FONT,
    fill = "#00000000",
    frameLine = line("#00000000", 0),
    insets = { left: 0, right: 0, top: 0, bottom: 0 },
  } = options;
  return ctx.addText(slide, {
    left,
    top,
    width,
    height,
    text: content,
    fontSize: size,
    color,
    bold,
    typeface: face,
    align,
    valign,
    fill,
    line: frameLine,
    insets,
  });
}

async function image(slide, ctx, options) {
  if (!exists(options.path)) return null;
  return ctx.addImage(slide, options);
}

function bg(slide, ctx, fill = C.white) {
  shape(slide, ctx, { left: 0, top: 0, width: ctx.W || W, height: ctx.H || H, fill, line: line(fill, 0) });
}

function seal(slide, ctx, { left = 34, top = 19, size = 34, dark = false } = {}) {
  const stroke = dark ? "#BFD9EF" : C.line2;
  const color = dark ? "#DDEEFF" : C.navy;
  shape(slide, ctx, { left, top, width: size, height: size, geometry: "ellipse", fill: "#FFFFFF00", line: line(stroke, 1.4) });
  shape(slide, ctx, { left: left + 6, top: top + 6, width: size - 12, height: size - 12, geometry: "ellipse", fill: "#FFFFFF00", line: line(stroke, 0.8) });
  text(slide, ctx, { left: left + 2, top: top + 8, width: size - 4, height: 18, content: "校", size: 12, color, bold: true, align: "center", valign: "middle" });
}

async function lightChrome(slide, ctx, { index, title, section = "毕业设计答辩", source = "" }) {
  bg(slide, ctx, C.white);
  shape(slide, ctx, { left: 0, top: 0, width: W, height: 58, fill: "#F3F7FB", line: line("#F3F7FB", 0) });
  shape(slide, ctx, { left: 46, top: 50, width: 1120, height: 2, fill: C.blue, line: line(C.blue, 0) });
  shape(slide, ctx, { left: 47, top: 22, width: 58, height: 24, geometry: "roundRect", fill: C.cyan, line: line(C.cyan, 0) });
  text(slide, ctx, { left: 47, top: 27, width: 58, height: 12, content: String(index).padStart(2, "0"), size: 9, color: C.white, bold: true, align: "center", valign: "middle", face: FONT_MONO });
  seal(slide, ctx, { left: 1162, top: 14, size: 42 });
  text(slide, ctx, { left: 46, top: 80, width: 960, height: 36, content: title, size: 25, color: C.navy, bold: true });
  text(slide, ctx, { left: 1060, top: 27, width: 95, height: 12, content: section, size: 8.5, color: C.muted, align: "right" });
  shape(slide, ctx, { left: 0, top: 690, width: W, height: 30, geometry: "roundRect", fill: "#EDF3F8", line: line("#EDF3F8", 0) });
  text(slide, ctx, { left: 50, top: 700, width: 900, height: 10, content: source ? `来源：${source}` : "来源：项目 README、论文正文与系统源码", size: 7.5, color: C.muted });
  text(slide, ctx, { left: 1160, top: 699, width: 36, height: 10, content: String(index).padStart(2, "0"), size: 7.5, color: C.muted, align: "right", face: FONT_MONO });
}

async function darkChrome(slide, ctx, { index, title, kicker = "", source = "" }) {
  bg(slide, ctx, C.dark);
  shape(slide, ctx, { left: 0, top: 0, width: W, height: H, fill: C.dark, line: line(C.dark, 0) });
  shape(slide, ctx, { left: 930, top: -72, width: 320, height: 210, geometry: "ellipse", fill: "#1C527F", line: line("#1C527F", 0) });
  shape(slide, ctx, { left: -86, top: 560, width: 360, height: 180, geometry: "ellipse", fill: "#1A4B75", line: line("#1A4B75", 0) });
  shape(slide, ctx, { left: 47, top: 28, width: 58, height: 24, geometry: "roundRect", fill: C.cyan, line: line(C.cyan, 0) });
  text(slide, ctx, { left: 47, top: 33, width: 58, height: 12, content: String(index).padStart(2, "0"), size: 9, color: C.white, bold: true, align: "center", valign: "middle", face: FONT_MONO });
  seal(slide, ctx, { left: 1136, top: 22, size: 44, dark: true });
  if (kicker) text(slide, ctx, { left: 46, top: 90, width: 780, height: 16, content: kicker.toUpperCase(), size: 9, color: "#9DD8E8", bold: true, face: FONT_MONO });
  text(slide, ctx, { left: 46, top: 120, width: 1050, height: 42, content: title, size: 27, color: C.white, bold: true });
  text(slide, ctx, { left: 50, top: 700, width: 900, height: 10, content: source ? `来源：${source}` : "来源：项目 README、论文正文与系统源码", size: 7.5, color: "#9DB9D2" });
  text(slide, ctx, { left: 1160, top: 699, width: 36, height: 10, content: String(index).padStart(2, "0"), size: 7.5, color: "#9DB9D2", align: "right", face: FONT_MONO });
}

function card(slide, ctx, { left, top, width, height, title, body, accent = C.blue, fill = C.white, stroke = C.line, titleSize = 14, bodySize = 11.2, titleColor = C.navy, bodyColor = C.text }) {
  const compact = height <= 64;
  shape(slide, ctx, { left, top, width, height, geometry: "roundRect", fill, line: line(stroke, 1) });
  shape(slide, ctx, { left: left + 14, top: top + 14, width: 4, height: Math.max(18, height - 28), fill: accent, line: line(accent, 0) });
  text(slide, ctx, { left: left + 28, top: top + (compact ? 10 : 14), width: width - 42, height: compact ? 16 : 21, content: title, size: compact ? 12.8 : titleSize, color: titleColor, bold: true });
  text(slide, ctx, { left: left + 28, top: top + (compact ? 30 : 42), width: width - 44, height: Math.max(12, height - (compact ? 36 : 50)), content: body, size: bodySize, color: bodyColor });
}

function label(slide, ctx, { left, top, width, textValue, fill = C.blue, color = C.white }) {
  shape(slide, ctx, { left, top, width, height: 23, geometry: "roundRect", fill, line: line(fill, 0) });
  text(slide, ctx, { left, top: top + 5, width, height: 10, content: textValue, size: 8.5, color, bold: true, align: "center", face: FONT });
}

function stat(slide, ctx, { left, top, width, value, labelText, accent = C.blue }) {
  shape(slide, ctx, { left, top, width, height: 74, geometry: "roundRect", fill: "#F9FBFE", line: line(C.line2, 1) });
  text(slide, ctx, { left, top: top + 11, width, height: 28, content: value, size: 24, color: accent, bold: true, align: "center", valign: "middle", face: FONT_MONO });
  text(slide, ctx, { left: left + 8, top: top + 44, width: width - 16, height: 18, content: labelText, size: 10, color: C.muted, align: "center", valign: "middle" });
}

function bulletList(slide, ctx, { left, top, width, items, size = 12, gap = 25, color = C.text, bulletColor = C.gold }) {
  items.forEach((item, idx) => {
    const y = top + idx * gap;
    shape(slide, ctx, { left, top: y + 6, width: 6, height: 6, geometry: "ellipse", fill: bulletColor, line: line(bulletColor, 0) });
    text(slide, ctx, { left: left + 16, top: y, width: width - 16, height: gap, content: item, size, color });
  });
}

function codeBox(slide, ctx, { left, top, width, height, title, lines, accent = C.cyan, footer = "" }) {
  shape(slide, ctx, { left, top, width, height, geometry: "roundRect", fill: "#143B60", line: line("#143B60", 0) });
  shape(slide, ctx, { left, top, width, height: 30, geometry: "roundRect", fill: "#1D527F", line: line("#1D527F", 0) });
  shape(slide, ctx, { left: left + 14, top: top + 9, width: 6, height: 12, fill: accent, line: line(accent, 0) });
  text(slide, ctx, { left: left + 30, top: top + 7, width: width - 40, height: 14, content: title, size: 10, color: C.white, bold: true, face: FONT_MONO });
  text(slide, ctx, { left: left + 18, top: top + 42, width: width - 36, height: height - 64, content: lines.join("\n"), size: 9.4, color: "#EAF6FF", face: FONT_MONO });
  if (footer) text(slide, ctx, { left: left + 18, top: top + height - 18, width: width - 36, height: 10, content: footer, size: 7.8, color: "#A7C7E6", face: FONT_MONO });
}

async function framedImage(slide, ctx, { left, top, width, height, title, imagePath, fit = "contain", accent = C.blue, pad = 14 }) {
  shape(slide, ctx, { left, top, width, height, geometry: "roundRect", fill: C.white, line: line(C.line, 1) });
  label(slide, ctx, { left: left + 14, top: top + 13, width: Math.min(220, width - 28), textValue: title, fill: accent });
  await image(slide, ctx, { left: left + pad, top: top + 42, width: width - pad * 2, height: height - 54, path: imagePath, fit, alt: title });
}

function placeholder(slide, ctx, { left, top, width, height, title, note, accent = C.gold }) {
  shape(slide, ctx, { left, top, width, height, geometry: "roundRect", fill: "#FBFCFE", line: line(C.line, 1) });
  label(slide, ctx, { left: left + 14, top: top + 14, width: 150, textValue: "真实截图预留位", fill: accent });
  shape(slide, ctx, { left: left + width / 2 - 30, top: top + 72, width: 60, height: 60, geometry: "roundRect", fill: "#FFFFFF00", line: line(accent, 2) });
  shape(slide, ctx, { left: left + width / 2 - 18, top: top + 88, width: 36, height: 24, geometry: "roundRect", fill: "#FFFFFF00", line: line(accent, 2) });
  text(slide, ctx, { left: left + 26, top: top + 144, width: width - 52, height: 24, content: title, size: 16, color: C.navy, bold: true, align: "center" });
  text(slide, ctx, { left: left + 26, top: top + 180, width: width - 52, height: 34, content: note, size: 10.5, color: C.muted, align: "center" });
}

function arrow(slide, ctx, { x1, y1, x2, y2, color = C.blue, labelText = "" }) {
  shape(slide, ctx, { left: x1, top: y1, width: Math.max(2, x2 - x1), height: 2, fill: color, line: line(color, 0) });
  shape(slide, ctx, { left: x2 - 8, top: y2 - 6, width: 0, height: 0, geometry: "triangle", fill: color, line: line(color, 0), rotate: 90 });
  if (labelText) text(slide, ctx, { left: x1, top: y1 - 22, width: Math.max(80, x2 - x1), height: 16, content: labelText, size: 9.5, color, align: "center" });
}

function miniTable(slide, ctx, { left, top, widths, rows, rowHeight = 44 }) {
  rows.forEach((row, r) => {
    let x = left;
    row.forEach((cell, c) => {
      const w = widths[c];
      const fill = r === 0 ? "#E8F0F8" : C.white;
      shape(slide, ctx, { left: x, top: top + r * rowHeight, width: w, height: rowHeight, fill, line: line(C.line, 1) });
      text(slide, ctx, { left: x + 10, top: top + r * rowHeight + 9, width: w - 20, height: rowHeight - 12, content: cell, size: r === 0 ? 10.5 : 10.2, color: r === 0 ? C.navy : C.text, bold: r === 0, valign: "middle" });
      x += w;
    });
  });
}

function sectionDivider(slide, ctx, { index, n, title, subtitle, points }) {
  darkChrome(slide, ctx, { index, title, kicker: `SECTION ${n}` });
  text(slide, ctx, { left: 48, top: 214, width: 760, height: 48, content: subtitle, size: 20, color: "#DCEAF8" });
  points.forEach((p, i) => {
    const left = 92 + i * 285;
    shape(slide, ctx, { left, top: 340, width: 230, height: 112, geometry: "roundRect", fill: "#173E66", line: line("#2A5C8A", 1) });
    text(slide, ctx, { left: left + 22, top: 364, width: 50, height: 26, content: `0${i + 1}`, size: 24, color: [C.cyan, C.gold, C.green][i] || C.cyan, bold: true, face: FONT_MONO });
    text(slide, ctx, { left: left + 22, top: 404, width: 186, height: 34, content: p, size: 15, color: C.white, bold: true });
  });
}

export async function slide01(presentation, ctx) {
  const slide = presentation.slides.add();
  await image(slide, ctx, { left: 0, top: 0, width: W, height: H, path: asset(ctx, "docs", "thesis-prep", "materials", "封面.png"), fit: "cover", alt: "cover background" });
  shape(slide, ctx, { left: 0, top: 0, width: W, height: H, fill: "#EAF3F9B8", line: line("#EAF3F9", 0) });
  shape(slide, ctx, { left: 78, top: 102, width: 560, height: 408, geometry: "roundRect", fill: "#FFFFFFEC", line: line(C.line, 1) });
  label(slide, ctx, { left: 104, top: 130, width: 126, textValue: "毕业设计答辩", fill: C.cyan });
  text(slide, ctx, { left: 104, top: 182, width: 482, height: 90, content: "基于 Web 的 Landsat 8\n遥感影像在线预处理系统", size: 30, color: C.navy, bold: true });
  text(slide, ctx, { left: 104, top: 296, width: 430, height: 38, content: "Remote Sensing Image Online Preprocessing Platform", size: 14, color: C.muted });
  card(slide, ctx, { left: 104, top: 362, width: 210, height: 78, title: "系统定位", body: "面向 Landsat 8/9 的本地化 Web 遥感预处理工作台。", accent: C.blue, bodySize: 10.6 });
  card(slide, ctx, { left: 336, top: 362, width: 210, height: 78, title: "答辩主线", body: "从需求、架构、实现到测试与结果证据。", accent: C.cyan, bodySize: 10.6 });
  shape(slide, ctx, { left: 750, top: 468, width: 310, height: 92, geometry: "roundRect", fill: "#FFFFFFD8", line: line("#D5E2EE", 1) });
  text(slide, ctx, { left: 778, top: 492, width: 260, height: 54, content: "答辩人：李旭东\n指导教师：待填写\n日期：2026 年 5 月", size: 12, color: C.navy, bold: true });
  seal(slide, ctx, { left: 1115, top: 48, size: 62 });
  return slide;
}

export async function slide02(presentation, ctx) {
  const slide = presentation.slides.add();
  await darkChrome(slide, ctx, { index: 2, title: "30 页答辩主线：从问题到可演示系统", kicker: "DEFENSE ROUTE", source: "README.md；论文第3-5章" });
  text(slide, ctx, { left: 48, top: 188, width: 420, height: 92, content: "本稿按正式答辩节奏展开：先说明为什么做，再说明系统怎么设计，随后用关键代码证明实现，最后以真实界面与测试结论收束。", size: 17, color: "#DCEAF8" });
  const items = [
    ["01", "选题背景", "问题、意义、目标"],
    ["02", "系统设计", "架构、模块、流程"],
    ["03", "核心实现", "算法、代码、难点"],
    ["04", "测试展示", "截图、验证、结论"],
  ];
  items.forEach((it, i) => {
    const left = 520 + i * 160;
    shape(slide, ctx, { left, top: 210, width: 136, height: 206, geometry: "roundRect", fill: "#173E66", line: line("#2B5D8B", 1) });
    text(slide, ctx, { left: left + 18, top: 238, width: 80, height: 28, content: it[0], size: 25, color: [C.cyan, C.blue, C.gold, C.green][i], bold: true, face: FONT_MONO });
    text(slide, ctx, { left: left + 18, top: 284, width: 108, height: 24, content: it[1], size: 17, color: C.white, bold: true });
    text(slide, ctx, { left: left + 18, top: 324, width: 108, height: 44, content: it[2], size: 11.5, color: "#CCE1F3" });
    shape(slide, ctx, { left: left + 18, top: 386, width: 44, height: 4, fill: [C.cyan, C.blue, C.gold, C.green][i], line: line([C.cyan, C.blue, C.gold, C.green][i], 0) });
  });
  card(slide, ctx, { left: 48, top: 496, width: 1110, height: 82, title: "新版设计原则", body: "30 页不是增加负担，而是把答辩信息拆成更清晰的镜头：每页只证明一个观点，评委可以顺着证据一路看到系统已经跑通。", accent: C.gold, fill: "#173E66", stroke: "#7FA5C8", titleColor: C.white, bodyColor: "#DCEAF8", bodySize: 12.2 });
  return slide;
}

export async function slide03(presentation, ctx) {
  const slide = presentation.slides.add();
  await lightChrome(slide, ctx, { index: 3, title: "答辩目录", source: "论文结构与项目 README" });
  const sections = [
    ["一、选题背景与需求分析", "研究背景、问题拆解、建设目标、系统边界"],
    ["二、系统总体设计", "技术路线、总体架构、前后端分层、核心数据流"],
    ["三、详细实现与关键代码", "单景处理、批量流程、在线下载、结果资产中心"],
    ["四、技术难点与解决方案", "产品级别兼容、异步执行、文件安全与结果回访"],
    ["五、系统测试与成果展示", "真实界面、测试口径、结论、后续展望"],
  ];
  sections.forEach((s, i) => {
    const top = 134 + i * 92;
    shape(slide, ctx, { left: 82, top, width: 84, height: 56, geometry: "roundRect", fill: i === 0 ? C.navy : "#EFF4F9", line: line(i === 0 ? C.navy : C.line, 1) });
    text(slide, ctx, { left: 82, top: top + 16, width: 84, height: 20, content: `0${i + 1}`, size: 18, color: i === 0 ? C.white : C.blue, bold: true, align: "center", face: FONT_MONO });
    card(slide, ctx, { left: 190, top: top - 2, width: 936, height: 60, title: s[0], body: s[1], accent: [C.blue, C.cyan, C.gold, C.green, C.orange][i], bodySize: 11 });
  });
  return slide;
}

export async function slide04(presentation, ctx) {
  const slide = presentation.slides.add();
  await lightChrome(slide, ctx, { index: 4, title: "研究背景：遥感数据应用对预处理提出更高要求", source: "docs/thesis-prep/materials/研究背景与意义（优化版）.png；论文第1章" });
  await framedImage(slide, ctx, { left: 46, top: 132, width: 520, height: 420, title: "背景图示", imagePath: asset(ctx, "docs", "thesis-prep", "materials", "研究背景与意义（优化版）.png"), fit: "contain" });
  card(slide, ctx, { left: 602, top: 132, width: 534, height: 92, title: "遥感影像应用场景广", body: "Landsat 数据广泛用于植被、水体、城市扩张、农业与生态监测。预处理质量直接影响后续指数计算与专题分析。", accent: C.blue });
  card(slide, ctx, { left: 602, top: 246, width: 534, height: 92, title: "传统处理链分散", body: "取数、波段处理、质量掩膜、裁剪、合成、结果管理通常分布在多个工具或脚本中，学习和复用成本较高。", accent: C.cyan });
  card(slide, ctx, { left: 602, top: 360, width: 534, height: 92, title: "Web 化工作台有现实意义", body: "把参数配置、任务提交、状态反馈、结果预览整合到浏览器界面，可降低实验门槛，也便于答辩演示与后续扩展。", accent: C.green });
  card(slide, ctx, { left: 602, top: 474, width: 534, height: 64, title: "选题落点", body: "以 Landsat 8 为核心，构建可运行、可展示、可扩展的在线预处理系统。", accent: C.gold, fill: C.paleGold, bodySize: 10.8 });
  return slide;
}

export async function slide05(presentation, ctx) {
  const slide = presentation.slides.add();
  await lightChrome(slide, ctx, { index: 5, title: "问题拆解：从单次处理到连续工作流", source: "README.md；论文第3章" });
  const pain = [
    ["数据入口", "本地上传、在线检索、不同产品级别输入规则不一致。"],
    ["处理链路", "L1 需要辐射定标与大气校正，L2 可按官方缩放系数直接分析。"],
    ["质量控制", "云、阴影、雪、卷云与饱和像元需要统一掩膜和摘要。"],
    ["批量复用", "多景数据处理不能只靠重复手动点击，需要流程化编排。"],
    ["结果回访", "输出文件需要可预览、可下载、可归档，而不是散落在目录中。"],
  ];
  pain.forEach((p, i) => {
    const left = 54 + (i % 3) * 386;
    const top = i < 3 ? 142 : 344;
    card(slide, ctx, { left, top, width: i < 3 ? 330 : 520, height: 138, title: p[0], body: p[1], accent: [C.blue, C.cyan, C.green, C.gold, C.orange][i], fill: [C.paleBlue, C.paleCyan, C.paleGreen, C.paleGold, "#FFF2EA"][i], bodySize: 13 });
  });
  card(slide, ctx, { left: 54, top: 544, width: 1104, height: 66, title: "系统设计应回答的问题", body: "如何让遥感预处理从“脚本片段”变成一套前后端协同、流程清晰、结果可追踪的实验工作台。", accent: C.navy, bodySize: 12.8 });
  return slide;
}

export async function slide06(presentation, ctx) {
  const slide = presentation.slides.add();
  sectionDivider(slide, ctx, {
    index: 6,
    n: "01",
    title: "一、选题背景与需求分析",
    subtitle: "先把系统要解决的对象讲清楚：为什么做、做什么、边界在哪里。",
    points: ["研究问题", "建设目标", "系统边界"],
  });
  return slide;
}

export async function slide07(presentation, ctx) {
  const slide = presentation.slides.add();
  await lightChrome(slide, ctx, { index: 7, title: "课题目标：构建可运行的在线预处理工作台", source: "docs/thesis-prep/materials/课题目标与系统定位（优化版）.png；README.md" });
  await framedImage(slide, ctx, { left: 350, top: 138, width: 650, height: 330, title: "目标与系统定位", imagePath: asset(ctx, "docs", "thesis-prep", "materials", "课题目标与系统定位（优化版）.png"), fit: "contain" });
  card(slide, ctx, { left: 56, top: 138, width: 260, height: 94, title: "目标 1：单景处理", body: "完成波段上传、产品级别识别、预处理与结果预览。", accent: C.blue });
  card(slide, ctx, { left: 56, top: 252, width: 260, height: 94, title: "目标 2：批量流程", body: "把多景处理步骤组织为流程图，并转为可执行任务。", accent: C.cyan });
  card(slide, ctx, { left: 56, top: 366, width: 260, height: 94, title: "目标 3：在线取数", body: "支持按 AOI 检索与下载遥感影像资产，形成数据入口。", accent: C.green });
  card(slide, ctx, { left: 56, top: 500, width: 1100, height: 64, title: "答辩表述", body: "本项目的价值不只在某个算法，而在于把“数据获取、处理执行、结果管理”串成可以演示和继续迭代的系统。", accent: C.gold, fill: C.paleGold, bodySize: 12.2 });
  return slide;
}

export async function slide08(presentation, ctx) {
  const slide = presentation.slides.add();
  await lightChrome(slide, ctx, { index: 8, title: "需求分析：功能需求与非功能需求", source: "README.md；论文第2-3章" });
  miniTable(slide, ctx, {
    left: 62,
    top: 142,
    widths: [190, 430, 430],
    rowHeight: 58,
    rows: [
      ["需求类型", "需求内容", "系统响应"],
      ["单景处理", "输入波段、MTL、QA 文件，提交异步处理任务。", "预处理链、任务状态、结果预览与摘要反馈。"],
      ["批量处理", "多个场景按流程节点执行，可配置裁剪、合成与输出。", "图结构解析、任务配置生成、进度与失败重试。"],
      ["在线下载", "按 AOI、时间、云量、传感器检索与下载。", "STAC 检索、资产勾选、浏览器/服务端下载。"],
      ["结果管理", "处理结果需要归档、分类、预览和下载。", "task_manifest、分类扫描、路径白名单与压缩下载。"],
      ["工程运行", "本地部署、前后端协同、演示稳定。", "FastAPI + Vue，配置项集中管理，异常回退。"],
    ],
  });
  return slide;
}

export async function slide09(presentation, ctx) {
  const slide = presentation.slides.add();
  await lightChrome(slide, ctx, { index: 9, title: "系统边界：主线聚焦 Landsat，下载模块适度扩展", source: "README.md；services/landsat_download.py" });
  stat(slide, ctx, { left: 74, top: 150, width: 160, value: "L1 / L2", labelText: "Landsat 产品级别", accent: C.blue });
  stat(slide, ctx, { left: 270, top: 150, width: 160, value: "13", labelText: "常用遥感指数", accent: C.cyan });
  stat(slide, ctx, { left: 466, top: 150, width: 160, value: "3", labelText: "主要页面模块", accent: C.green });
  stat(slide, ctx, { left: 662, top: 150, width: 160, value: "4", labelText: "核心能力链路", accent: C.gold });
  stat(slide, ctx, { left: 858, top: 150, width: 160, value: "QA", labelText: "质量掩膜控制", accent: C.orange });
  card(slide, ctx, { left: 74, top: 286, width: 520, height: 132, title: "主处理边界", body: "预处理主链面向 Landsat 8/9，强调 L1/L2 产品兼容、质量控制、合成和指数计算。Sentinel-2 L2A 作为新增入口用于扩展 APGI 等处理能力。", accent: C.blue, fill: C.paleBlue, bodySize: 12.3 });
  card(slide, ctx, { left: 636, top: 286, width: 520, height: 132, title: "下载扩展边界", body: "在线检索下载模块支持 Landsat 7/8/9 与 Sentinel-2，重点承担数据入口、资产选择和服务端下载队列功能。", accent: C.green, fill: C.paleGreen, bodySize: 12.3 });
  card(slide, ctx, { left: 74, top: 470, width: 1082, height: 68, title: "真实性说明", body: "答辩中不虚构精度提升百分比，重点展示已实现的功能链路、源码证据、真实界面与测试结论。", accent: C.gold, fill: C.paleGold, bodySize: 12.4 });
  return slide;
}

export async function slide10(presentation, ctx) {
  const slide = presentation.slides.add();
  await lightChrome(slide, ctx, { index: 10, title: "技术路线：数据、处理、编排、展示四层闭环", source: "README.md；论文第3章" });
  const steps = [
    ["数据入口", "本地上传\n在线 STAC 检索\nAOI 配置"],
    ["预处理链", "L1 辐射定标\nL2 缩放直用\nQA 掩膜"],
    ["任务编排", "异步提交\n批量图执行\n失败回退"],
    ["结果资产", "预览图\n清单文件\n分类下载"],
  ];
  steps.forEach((s, i) => {
    const left = 72 + i * 280;
    shape(slide, ctx, { left, top: 178, width: 210, height: 190, geometry: "roundRect", fill: [C.paleBlue, C.paleCyan, C.paleGreen, C.paleGold][i], line: line(C.line2, 1) });
    text(slide, ctx, { left: left + 22, top: 204, width: 166, height: 24, content: s[0], size: 18, color: C.navy, bold: true, align: "center" });
    text(slide, ctx, { left: left + 28, top: 258, width: 154, height: 76, content: s[1], size: 13.2, color: C.text, align: "center" });
    if (i < 3) arrow(slide, ctx, { x1: left + 218, y1: 270, x2: left + 270, y2: 270, color: C.blue });
  });
  card(slide, ctx, { left: 72, top: 450, width: 1050, height: 80, title: "路线概括", body: "以 Web 工作台作为交互入口，以 FastAPI 服务组织任务，以处理器和服务模块承担计算与资产管理，形成从数据到成果的一体化闭环。", accent: C.gold, bodySize: 12.4 });
  return slide;
}

export async function slide11(presentation, ctx) {
  const slide = presentation.slides.add();
  sectionDivider(slide, ctx, {
    index: 11,
    n: "02",
    title: "二、系统总体设计",
    subtitle: "这一部分回答：系统由哪些层组成，数据如何流动，核心处理链怎么组织。",
    points: ["总体架构", "数据流", "模块职责"],
  });
  return slide;
}

export async function slide12(presentation, ctx) {
  const slide = presentation.slides.add();
  await lightChrome(slide, ctx, { index: 12, title: "系统总体架构：前端工作台 + 后端服务 + 核心处理", source: "docs/thesis-prep/materials/系统总体架构（重点优化）.png；README.md" });
  await framedImage(slide, ctx, { left: 58, top: 132, width: 560, height: 430, title: "总体架构图", imagePath: asset(ctx, "docs", "thesis-prep", "materials", "系统总体架构（重点优化）.png"), fit: "contain" });
  card(slide, ctx, { left: 660, top: 132, width: 464, height: 76, title: "前端表现层", body: "Vue 3 + Vite + OpenLayers + Vue Flow，负责参数配置、空间交互和流程画布。", accent: C.blue });
  card(slide, ctx, { left: 660, top: 224, width: 464, height: 76, title: "接口服务层", body: "FastAPI 负责异步任务提交、状态查询、文件扫描、下载管理和结果访问。", accent: C.cyan });
  card(slide, ctx, { left: 660, top: 316, width: 464, height: 86, title: "核心处理层", body: "处理器统一执行辐射定标、大气校正、质量掩膜、裁剪、合成与指数计算。", accent: C.green });
  card(slide, ctx, { left: 660, top: 418, width: 464, height: 76, title: "数据资产层", body: "data、output、temp、cache 与 task_manifest 共同支撑结果归档和回访。", accent: C.gold });
  return slide;
}

export async function slide13(presentation, ctx) {
  const slide = presentation.slides.add();
  await lightChrome(slide, ctx, { index: 13, title: "前后端分层：界面交互与计算任务解耦", source: "README.md；frontend-vue/src/components；remote_sensing_tools/api" });
  const cols = [
    ["浏览器工作台", "参数表单\nAOI 地图\n流程画布\n结果预览", C.paleBlue, C.blue],
    ["FastAPI 接口", "上传校验\n任务提交\n状态查询\n文件访问", C.paleCyan, C.cyan],
    ["服务模块", "批量队列\n图执行器\n下载服务\n结果扫描", C.paleGreen, C.green],
    ["核心算法", "辐射定标\n大气校正\n质量掩膜\n指数合成", C.paleGold, C.gold],
  ];
  cols.forEach((c, i) => {
    const left = 72 + i * 275;
    shape(slide, ctx, { left, top: 150, width: 220, height: 300, geometry: "roundRect", fill: c[2], line: line(C.line2, 1) });
    text(slide, ctx, { left: left + 22, top: 180, width: 176, height: 28, content: c[0], size: 18, color: C.navy, bold: true, align: "center" });
    text(slide, ctx, { left: left + 36, top: 250, width: 148, height: 130, content: c[1], size: 16, color: C.text, align: "center" });
    shape(slide, ctx, { left: left + 65, top: 398, width: 90, height: 5, fill: c[3], line: line(c[3], 0) });
    if (i < 3) arrow(slide, ctx, { x1: left + 226, y1: 300, x2: left + 268, y2: 300, color: C.blue });
  });
  card(slide, ctx, { left: 72, top: 510, width: 1045, height: 66, title: "设计收益", body: "前端只负责可视化配置和反馈，后端集中处理任务状态和文件安全，核心算法保持独立，便于后续扩展和维护。", accent: C.navy, bodySize: 12.3 });
  return slide;
}

export async function slide14(presentation, ctx) {
  const slide = presentation.slides.add();
  await lightChrome(slide, ctx, { index: 14, title: "核心数据流：从输入影像到可回访结果", source: "README.md；docs/thesis-prep/chapters/03-第3章-系统分析与总体设计.md" });
  const nodes = [
    ["输入数据", "波段文件\nMTL\nQA_PIXEL"],
    ["任务配置", "产品级别\nAOI\n处理参数"],
    ["处理执行", "定标/校正\n掩膜/裁剪\n合成/指数"],
    ["结果生成", "预览图\nGeoTIFF\n摘要信息"],
    ["资产管理", "task_manifest\n分类扫描\n下载访问"],
  ];
  nodes.forEach((n, i) => {
    const left = 74 + i * 220;
    card(slide, ctx, { left, top: 188, width: 168, height: 136, title: n[0], body: n[1], accent: [C.blue, C.cyan, C.green, C.gold, C.orange][i], fill: "#FBFDFF", bodySize: 12.4 });
    if (i < 4) arrow(slide, ctx, { x1: left + 176, y1: 258, x2: left + 214, y2: 258, color: C.blue });
  });
  card(slide, ctx, { left: 74, top: 416, width: 1040, height: 72, title: "闭环关键", body: "系统不是只生成一个输出文件，而是把参数、状态、结果与访问路径组织在一起，使任务结果能够被再次查看和下载。", accent: C.gold, fill: C.paleGold, bodySize: 12.6 });
  return slide;
}

export async function slide15(presentation, ctx) {
  const slide = presentation.slides.add();
  await lightChrome(slide, ctx, { index: 15, title: "L1 / L2 双链路：同一工作台适配不同产品级别", source: "remote_sensing_tools/core/processor.py；README.md" });
  card(slide, ctx, { left: 82, top: 190, width: 180, height: 86, title: "影像输入", body: "波段文件\nMTL 元数据\nQA 文件", accent: C.blue });
  arrow(slide, ctx, { x1: 270, y1: 232, x2: 330, y2: 232, color: C.blue });
  card(slide, ctx, { left: 342, top: 142, width: 170, height: 86, title: "L1 链路", body: "DN → 辐射亮度\nTOA 反射率", accent: C.blue, fill: C.paleBlue });
  arrow(slide, ctx, { x1: 520, y1: 184, x2: 580, y2: 184, color: C.blue });
  card(slide, ctx, { left: 592, top: 142, width: 190, height: 86, title: "大气校正", body: "优先 Py6S\n失败回退 DOS", accent: C.cyan, fill: C.paleCyan });
  arrow(slide, ctx, { x1: 790, y1: 184, x2: 850, y2: 184, color: C.blue });
  card(slide, ctx, { left: 862, top: 142, width: 190, height: 86, title: "L1 输出", body: "处理波段\n合成图和指数图", accent: C.blue, fill: C.paleBlue });
  card(slide, ctx, { left: 342, top: 338, width: 170, height: 86, title: "L2 链路", body: "官方缩放系数\n表面反射率", accent: C.green, fill: C.paleGreen });
  arrow(slide, ctx, { x1: 520, y1: 380, x2: 580, y2: 380, color: C.green });
  card(slide, ctx, { left: 592, top: 338, width: 190, height: 86, title: "直接分析", body: "跳过重复辐射\n和大气校正", accent: C.green, fill: C.paleGreen });
  arrow(slide, ctx, { x1: 790, y1: 380, x2: 850, y2: 380, color: C.green });
  card(slide, ctx, { left: 862, top: 338, width: 190, height: 86, title: "L2 输出", body: "统一结果结构\n便于管理", accent: C.green, fill: C.paleGreen });
  card(slide, ctx, { left: 82, top: 520, width: 970, height: 64, title: "质量控制贯穿两条链路", body: "QA_PIXEL 用于云、阴影、雪、卷云掩膜；QA_RADSAT 用于饱和像元控制，并返回质量摘要与有效像元比例。", accent: C.gold, bodySize: 12.1 });
  return slide;
}

export async function slide16(presentation, ctx) {
  const slide = presentation.slides.add();
  sectionDivider(slide, ctx, {
    index: 16,
    n: "03",
    title: "三、详细实现与功能模块",
    subtitle: "这一部分把系统拆成可展示、可验证的功能模块。",
    points: ["单景处理", "批量编排", "下载与资产"],
  });
  return slide;
}

export async function slide17(presentation, ctx) {
  const slide = presentation.slides.add();
  await lightChrome(slide, ctx, { index: 17, title: "单景预处理模块：上传、执行、预览一体化", source: "README.md；frontend-vue/src/components" });
  const items = [
    ["输入组织", "波段文件、MTL、QA_PIXEL、QA_RADSAT 与 AOI 参数集中配置。"],
    ["异步提交", "前端提交任务后，后端执行处理链并返回任务状态。"],
    ["步骤反馈", "处理进度、步骤状态和异常信息在界面中持续更新。"],
    ["结果预览", "处理结果按类型展示路径、预览图和下载入口。"],
  ];
  items.forEach((it, i) => {
    card(slide, ctx, { left: 72 + (i % 2) * 555, top: 146 + Math.floor(i / 2) * 176, width: 500, height: 126, title: it[0], body: it[1], accent: [C.blue, C.cyan, C.green, C.gold][i], fill: [C.paleBlue, C.paleCyan, C.paleGreen, C.paleGold][i], bodySize: 12.6 });
  });
  card(slide, ctx, { left: 72, top: 518, width: 1055, height: 64, title: "模块价值", body: "单景处理页承担答辩演示的主入口，能直接证明前端参数、后端任务和结果预览三部分已经打通。", accent: C.navy, bodySize: 12.4 });
  return slide;
}

export async function slide18(presentation, ctx) {
  const slide = presentation.slides.add();
  await lightChrome(slide, ctx, { index: 18, title: "AOI 空间交互：把地图选择转化为处理约束", source: "frontend-vue；OpenLayers 10；论文第4章" });
  shape(slide, ctx, { left: 74, top: 144, width: 520, height: 350, geometry: "roundRect", fill: "#EDF5F1", line: line(C.line2, 1) });
  shape(slide, ctx, { left: 102, top: 174, width: 464, height: 286, geometry: "roundRect", fill: "#DDEBD8", line: line("#A7C3A2", 1) });
  shape(slide, ctx, { left: 210, top: 230, width: 240, height: 130, fill: "#FFFFFF33", line: line(C.blue, 2) });
  shape(slide, ctx, { left: 318, top: 272, width: 14, height: 14, geometry: "ellipse", fill: C.orange, line: line(C.orange, 0) });
  text(slide, ctx, { left: 102, top: 468, width: 464, height: 22, content: "矢量示意：AOI 框选 / 矢量导入 / 坐标约束", size: 12, color: C.muted, align: "center" });
  card(slide, ctx, { left: 640, top: 144, width: 480, height: 96, title: "交互输入", body: "用户可以通过地图框选、坐标输入或矢量文件导入 AOI。", accent: C.blue });
  card(slide, ctx, { left: 640, top: 266, width: 480, height: 96, title: "后端约束", body: "AOI 参数进入裁剪、场景筛选和在线检索流程，成为处理范围边界。", accent: C.cyan });
  card(slide, ctx, { left: 640, top: 388, width: 480, height: 96, title: "答辩证据", body: "AOI 配置页的真实截图将用于证明空间交互已经落地。", accent: C.gold, fill: C.paleGold });
  return slide;
}

export async function slide19(presentation, ctx) {
  const slide = presentation.slides.add();
  await lightChrome(slide, ctx, { index: 19, title: "批量处理模块：从节点画布到可执行作业", source: "remote_sensing_tools/services/graph_executor.py；Vue Flow" });
  const nodes = [
    ["数据目录", C.blue],
    ["场景筛选", C.cyan],
    ["条件裁剪", C.green],
    ["镶嵌/合成", C.gold],
    ["输出路径", C.orange],
  ];
  nodes.forEach((n, i) => {
    const left = 88 + i * 205;
    shape(slide, ctx, { left, top: 190, width: 150, height: 84, geometry: "roundRect", fill: "#FBFDFF", line: line(n[1], 1.5) });
    text(slide, ctx, { left: left + 16, top: 216, width: 118, height: 24, content: n[0], size: 15, color: C.navy, bold: true, align: "center" });
    if (i < 4) arrow(slide, ctx, { x1: left + 158, y1: 232, x2: left + 198, y2: 232, color: C.blue });
  });
  card(slide, ctx, { left: 88, top: 354, width: 500, height: 130, title: "前端职责", body: "Vue Flow 负责节点展示、参数编辑和连接关系维护，把复杂批处理流程转成可理解的可视化画布。", accent: C.blue, fill: C.paleBlue, bodySize: 12.5 });
  card(slide, ctx, { left: 632, top: 354, width: 500, height: 130, title: "后端职责", body: "图执行器判断起终点可达性、拓扑顺序、节点约束和场景上下文，再生成 BatchJobConfig。", accent: C.green, fill: C.paleGreen, bodySize: 12.5 });
  return slide;
}

export async function slide20(presentation, ctx) {
  const slide = presentation.slides.add();
  await lightChrome(slide, ctx, { index: 20, title: "在线检索下载与结果资产中心", source: "services/landsat_download.py；services/task_results.py" });
  card(slide, ctx, { left: 70, top: 138, width: 330, height: 150, title: "在线检索下载", body: "通过 STAC 检索 Landsat 7/8/9 与 Sentinel-2，支持 AOI、云量、时间范围、资产勾选和服务端下载。", accent: C.blue, fill: C.paleBlue, bodySize: 12.2 });
  card(slide, ctx, { left: 440, top: 138, width: 330, height: 150, title: "下载队列与代理", body: "服务端下载支持目录配置、代理参数、重试与并发控制，适合网络条件不稳定时演示。", accent: C.cyan, fill: C.paleCyan, bodySize: 12.2 });
  card(slide, ctx, { left: 810, top: 138, width: 330, height: 150, title: "结果资产中心", body: "扫描当前任务与历史任务，按 processed、composite、mask、metadata 等类别归档。", accent: C.green, fill: C.paleGreen, bodySize: 12.2 });
  placeholder(slide, ctx, { left: 70, top: 356, width: 250, height: 188, title: "下载检索页", note: "后续替换为真实 STAC 检索界面", accent: C.blue });
  placeholder(slide, ctx, { left: 360, top: 356, width: 250, height: 188, title: "结果资产中心", note: "后续替换为任务结果扫描界面", accent: C.cyan });
  placeholder(slide, ctx, { left: 650, top: 356, width: 250, height: 188, title: "真彩色结果", note: "后续替换为真实处理输出", accent: C.green });
  placeholder(slide, ctx, { left: 940, top: 356, width: 250, height: 188, title: "NDVI 结果", note: "后续替换为真实指数结果", accent: C.gold });
  return slide;
}

export async function slide21(presentation, ctx) {
  const slide = presentation.slides.add();
  sectionDivider(slide, ctx, {
    index: 21,
    n: "04",
    title: "四、关键算法、代码与技术难点",
    subtitle: "用源码证据说明系统不是静态页面，而是真正把处理链和工程约束实现出来。",
    points: ["处理算法", "关键代码", "难点拆解"],
  });
  return slide;
}

export async function slide22(presentation, ctx) {
  const slide = presentation.slides.add();
  await darkChrome(slide, ctx, { index: 22, title: "关键算法：辐射定标、大气校正与质量掩膜", kicker: "ALGORITHM EVIDENCE", source: "remote_sensing_tools/core/processor.py；operations" });
  card(slide, ctx, { left: 48, top: 186, width: 320, height: 118, title: "算法链路", body: "L1 产品执行辐射定标、TOA 反射率、大气校正；L2 产品按官方缩放系数转为表面反射率。", accent: C.cyan, fill: "#E6F8FA", bodySize: 11.2 });
  card(slide, ctx, { left: 48, top: 326, width: 320, height: 118, title: "质量控制", body: "QA_PIXEL 与 QA_RADSAT 用于云、阴影、雪、卷云和饱和像元掩膜，并返回有效像元摘要。", accent: C.green, fill: "#EDF8EC", bodySize: 11.2 });
  codeBox(slide, ctx, {
    left: 420,
    top: 188,
    width: 740,
    height: 258,
    title: "processor.py / processing decision",
    lines: [
      "product_level = self._normalize_product_level(product_level)",
      "if product_level == 'L2':",
      "    reflectance = self._load_l2_surface_reflectance(band_path, band_name)",
      "else:",
      "    radiance = self._dn_to_radiance(dn, metadata, band_name)",
      "    reflectance = self._radiance_to_toa_reflectance(radiance, metadata)",
      "    reflectance, method = self._apply_atmospheric_correction(...)",
      "qa_summary = summarize_qa_pixel(qa_band_path)",
      "valid_mask = build_quality_mask(qa_pixel, qa_radsat)",
    ],
    footer: "核心思想：按产品级别选择处理链，同时保留统一输出结构。",
  });
  card(slide, ctx, { left: 48, top: 496, width: 1112, height: 66, title: "答辩讲法", body: "这里不用展开每个遥感公式，重点说明系统如何在工程上处理 L1/L2 差异，并把质量控制接入整个结果链路。", accent: C.gold, fill: "#FFF4E0", bodySize: 11.8 });
  return slide;
}

export async function slide23(presentation, ctx) {
  const slide = presentation.slides.add();
  await darkChrome(slide, ctx, { index: 23, title: "关键代码 1：L1 / L2 双链路与 6S 失败回退", kicker: "CODE PROOF - PROCESSOR", source: "remote_sensing_tools/core/processor.py；core/constants.py" });
  codeBox(slide, ctx, {
    left: 50,
    top: 188,
    width: 520,
    height: 318,
    title: "processor.py / _apply_atmospheric_correction",
    lines: [
      "normalized_method = str(atm_correction_method or 'DOS').upper()",
      "if normalized_method not in ('NONE', '6S'):",
      "    corrected = dark_object_subtraction(reflectance)",
      "    return corrected, 'DOS'",
      "",
      "try:",
      "    corrected = self.sixs_atmospheric_correction(reflectance, band_name)",
      "    return corrected, '6S'",
      "except Exception as exc:",
      "    logger.warning('6S failed, fallback to DOS')",
      "    corrected = dark_object_subtraction(reflectance)",
      "    return corrected, 'DOS(6S失败回退)'",
    ],
  });
  codeBox(slide, ctx, {
    left: 610,
    top: 188,
    width: 520,
    height: 214,
    title: "constants.py / product-aware steps",
    lines: [
      "LANDSAT_L2_SR_SCALE = 0.0000275",
      "LANDSAT_L2_SR_OFFSET = -0.2",
      "PROGRESS_STEPS = [",
      "  {'id': 'calibration', 'title': '辐射定标'},",
      "  {'id': 'correction', 'title': '大气校正'},",
      "  {'id': 'composite', 'title': '波段合成'},",
      "  {'id': 'indices', 'title': '结果导出'},",
      "]",
    ],
    accent: C.green,
  });
  card(slide, ctx, { left: 610, top: 438, width: 520, height: 68, title: "技术点", body: "失败回退不是“兜底文字”，而是保证演示和批处理任务在依赖不完整时仍能完成。", accent: C.gold, fill: "#FFF4E0", bodySize: 11.6 });
  return slide;
}

export async function slide24(presentation, ctx) {
  const slide = presentation.slides.add();
  await darkChrome(slide, ctx, { index: 24, title: "关键代码 2：流程画布如何变成批处理任务", kicker: "CODE PROOF - GRAPH EXECUTOR", source: "remote_sensing_tools/services/graph_executor.py" });
  codeBox(slide, ctx, {
    left: 50,
    top: 184,
    width: 540,
    height: 330,
    title: "graph_executor.py / build_job_configs",
    lines: [
      "output_node = self._find_node(nodes, 'output')",
      "start_node = self._find_node(nodes, 'input')",
      "forward_reachable = self._reachable_nodes(start_node['id'], edges)",
      "backward_reachable = self._reverse_reachable_nodes(output_node['id'], edges)",
      "active_node_ids = forward_reachable & backward_reachable",
      "sorted_ids = self._topological_sort(active_nodes, active_edges)",
      "ctx = self._extract_context(sorted_ids, nodes, edges)",
      "errors.extend(self._validate_graph(ctx, sorted_ids))",
      "configs = [self._build_single_config(scene, ctx) for scene in scenes]",
    ],
  });
  codeBox(slide, ctx, {
    left: 630,
    top: 184,
    width: 500,
    height: 224,
    title: "graph_executor.py / Kahn topological sort",
    lines: [
      "in_degree = defaultdict(int)",
      "queue = deque([node_id for node_id in nodes if in_degree[node_id] == 0])",
      "while queue:",
      "    node_id = queue.popleft()",
      "    result.append(node_id)",
      "    for nxt in adj[node_id]:",
      "        in_degree[nxt] -= 1",
      "        if in_degree[nxt] == 0:",
      "            queue.append(nxt)",
    ],
    accent: C.green,
  });
  card(slide, ctx, { left: 630, top: 448, width: 500, height: 66, title: "技术点", body: "流程图必须先验证拓扑关系和节点约束，再转换为 BatchJobConfig，避免无效画布直接进入执行阶段。", accent: C.gold, fill: "#FFF4E0", bodySize: 11.6 });
  return slide;
}

export async function slide25(presentation, ctx) {
  const slide = presentation.slides.add();
  await darkChrome(slide, ctx, { index: 25, title: "关键代码 3：STAC 检索下载与结果资产组织", kicker: "CODE PROOF - DOWNLOAD & ASSET", source: "services/landsat_download.py；services/task_results.py" });
  codeBox(slide, ctx, {
    left: 50,
    top: 180,
    width: 520,
    height: 238,
    title: "landsat_download.py / collection config",
    lines: [
      "COLLECTIONS = {",
      "  'landsat': {'collection': 'landsat-c2-l2', 'platform_tokens': (...)},",
      "  'landsat-7': {'collection': 'landsat-c2-l2', 'platform_tokens': (...)},",
      "  'sentinel-2': {'collection': 'sentinel-2-l2a', 'platform_tokens': (...)},",
      "}",
      "self._download_semaphore = asyncio.Semaphore(max_concurrent_downloads)",
      "self._set_proxy_state(enabled=..., proxy_url=..., no_proxy=...)",
    ],
  });
  codeBox(slide, ctx, {
    left: 610,
    top: 180,
    width: 520,
    height: 238,
    title: "task_results.py / result organization",
    lines: [
      "manifest = load_task_manifest(task_dir)",
      "items = scan_result_files(task_dir)",
      "groups = classify_result_assets(items)",
      "previewable = is_previewable_suffix(path.suffix)",
      "download_url = build_safe_download_url(path)",
      "return {'processed': ..., 'composite': ..., 'mask': ..., 'metadata': ...}",
    ],
    accent: C.green,
  });
  card(slide, ctx, { left: 50, top: 460, width: 1080, height: 68, title: "技术点", body: "下载和结果管理是工程完整性的关键：系统不仅能算，还能取数、归档、预览、下载，并把历史任务重新组织起来。", accent: C.gold, fill: "#FFF4E0", bodySize: 11.8 });
  return slide;
}

export async function slide26(presentation, ctx) {
  const slide = presentation.slides.add();
  await lightChrome(slide, ctx, { index: 26, title: "技术难点与解决方案：三个工程问题", source: "README.md；论文第4章；源码实现" });
  card(slide, ctx, { left: 62, top: 144, width: 350, height: 320, title: "难点 1：产品级别兼容", body: "问题：L1 与 L2 的输入语义不同，不能套同一条处理链。\n\n解决：通过产品级别标准化、L2 缩放系数和大气校正回退，把两条链路收敛到统一输出结构。", accent: C.blue, fill: C.paleBlue, bodySize: 12.2 });
  card(slide, ctx, { left: 432, top: 144, width: 350, height: 320, title: "难点 2：流程图可执行化", body: "问题：前端画布只是结构表达，不能直接处理数据。\n\n解决：可达性分析、Kahn 拓扑排序、节点约束校验和上下文抽取，将图结构转换为批处理配置。", accent: C.cyan, fill: C.paleCyan, bodySize: 12.2 });
  card(slide, ctx, { left: 802, top: 144, width: 350, height: 320, title: "难点 3：结果可回访", body: "问题：处理完成后如果只有散落文件，系统难以演示历史成果。\n\n解决：用 task_manifest、结果分类、预览后缀和路径白名单，把文件变成可追踪资产。", accent: C.green, fill: C.paleGreen, bodySize: 12.2 });
  card(slide, ctx, { left: 62, top: 520, width: 1090, height: 62, title: "答辩话术", body: "技术难点不要讲成“代码很多”，而要讲成“我解决了产品差异、流程执行和结果组织三个工程问题”。", accent: C.gold, fill: C.paleGold, bodySize: 12 });
  return slide;
}

export async function slide27(presentation, ctx) {
  const slide = presentation.slides.add();
  await lightChrome(slide, ctx, { index: 27, title: "工程保障：异步任务、状态反馈与安全访问", source: "README.md；remote_sensing_tools/services；settings" });
  const items = [
    ["异步任务", "避免浏览器长时间阻塞；任务状态由后端持续维护。"],
    ["失败回退", "6S 失败时回退 DOS；下载失败可重试，减少演示中断。"],
    ["路径安全", "结果访问通过白名单与安全下载 URL 管理。"],
    ["配置集中", "HOST、PORT、DATA_DIR、OUTPUT_DIR、代理和下载目录由环境变量控制。"],
  ];
  items.forEach((it, i) => {
    card(slide, ctx, { left: 70 + (i % 2) * 550, top: 142 + Math.floor(i / 2) * 174, width: 500, height: 122, title: it[0], body: it[1], accent: [C.blue, C.cyan, C.green, C.gold][i], fill: [C.paleBlue, C.paleCyan, C.paleGreen, C.paleGold][i], bodySize: 12.3 });
  });
  card(slide, ctx, { left: 70, top: 514, width: 1050, height: 64, title: "为什么要讲工程保障", body: "答辩现场最重要的是系统能稳定演示。工程保障说明项目不只是算法实验，而是接近真实使用场景的 Web 系统。", accent: C.navy, bodySize: 12.2 });
  return slide;
}

export async function slide28(presentation, ctx) {
  const slide = presentation.slides.add();
  await lightChrome(slide, ctx, { index: 28, title: "真实界面展示：单景处理与 AOI 配置", source: "docs/thesis-prep/materials/screenshots/ss-4-01；ss-4-02" });
  await framedImage(slide, ctx, { left: 50, top: 132, width: 760, height: 472, title: "真实截图：单景处理页", imagePath: asset(ctx, "docs", "thesis-prep", "materials", "screenshots", "ss-4-01-single-task-overview.png"), fit: "contain" });
  await framedImage(slide, ctx, { left: 838, top: 132, width: 336, height: 206, title: "真实截图：AOI 配置", imagePath: asset(ctx, "docs", "thesis-prep", "materials", "screenshots", "ss-4-02-single-task-aoi-config.png"), fit: "contain", accent: C.cyan });
  card(slide, ctx, { left: 838, top: 366, width: 336, height: 138, title: "这页证明什么", body: "系统已经打通“参数配置 → 异步执行 → 状态反馈 → 结果预览”的单景处理链路。", accent: C.green, fill: C.paleGreen, bodySize: 12 });
  card(slide, ctx, { left: 50, top: 620, width: 1124, height: 52, title: "讲解提示", body: "不要逐项念表单，重点讲这张界面如何证明系统前后端交互和真实运行能力。", accent: C.gold, bodySize: 10.2 });
  return slide;
}

export async function slide29(presentation, ctx) {
  const slide = presentation.slides.add();
  await lightChrome(slide, ctx, { index: 29, title: "真实界面与结果预留：批量流程、下载和典型输出", source: "docs/thesis-prep/materials/screenshots/ss-4-03；后续运行截图预留" });
  await framedImage(slide, ctx, { left: 310, top: 132, width: 620, height: 380, title: "真实截图：批量流程画布", imagePath: asset(ctx, "docs", "thesis-prep", "materials", "screenshots", "ss-4-03-batch-canvas-overview.png"), fit: "contain", accent: C.blue });
  card(slide, ctx, { left: 54, top: 132, width: 240, height: 128, title: "批量处理价值", body: "节点画布把重复步骤抽象为流程，后端解析成可执行批处理作业。", accent: C.cyan, fill: C.paleCyan, bodySize: 11.2 });
  placeholder(slide, ctx, { left: 954, top: 132, width: 190, height: 170, title: "下载检索页", note: "补充真实运行截图", accent: C.blue });
  placeholder(slide, ctx, { left: 954, top: 330, width: 190, height: 170, title: "结果中心页", note: "补充真实运行截图", accent: C.green });
  card(slide, ctx, { left: 54, top: 532, width: 1090, height: 60, title: "讲解提示", body: "批量画布页用于证明“流程可配置”；预留位用于后续替换在线下载、结果中心、真彩色与 NDVI 等真实输出截图。", accent: C.gold, fill: C.paleGold, bodySize: 11.5 });
  return slide;
}

export async function slide30(presentation, ctx) {
  const slide = presentation.slides.add();
  await lightChrome(slide, ctx, { index: 30, title: "测试结论、后续工作与答辩收束", source: "docs/thesis-prep/chapters/05-第5章-系统测试与结果分析.md；README.md" });
  miniTable(slide, ctx, {
    left: 52,
    top: 136,
    widths: [170, 450, 150],
    rowHeight: 48,
    rows: [
      ["测试项", "验证内容", "现有结论"],
      ["单景预处理", "L1/L2 分支、AOI 裁剪、合成、指数、状态轮询", "符合预期"],
      ["批量处理", "流程图校验、拓扑排序、任务配置生成、失败提示", "符合预期"],
      ["在线检索下载", "AOI 检索、资产选择、代理与下载目录配置", "符合预期"],
      ["结果资产中心", "task_manifest 扫描、分类预览、下载访问", "符合预期"],
    ],
  });
  card(slide, ctx, { left: 840, top: 136, width: 320, height: 116, title: "结论", body: "系统已形成可演示、可扩展、具备工程闭环意识的遥感影像在线预处理平台原型。", accent: C.blue, fill: C.paleBlue, bodySize: 12 });
  card(slide, ctx, { left: 840, top: 276, width: 320, height: 116, title: "不足与展望", body: "后续可补充更多真实结果截图、处理时间统计、精度对比和更完善的数据集验证。", accent: C.gold, fill: C.paleGold, bodySize: 12 });
  bulletList(slide, ctx, { left: 858, top: 432, width: 300, items: ["答辩时保持真实口径。", "现场演示优先走稳定流程。", "截图预留位用最新运行结果替换。"], size: 11.2, gap: 24 });
  shape(slide, ctx, { left: 52, top: 558, width: 1108, height: 86, geometry: "roundRect", fill: "#EAF3FA", line: line(C.line2, 1) });
  text(slide, ctx, { left: 82, top: 584, width: 520, height: 28, content: "请各位老师批评指正", size: 24, color: C.navy, bold: true });
  text(slide, ctx, { left: 744, top: 590, width: 360, height: 20, content: "THANK YOU", size: 18, color: C.blue, bold: true, align: "right", face: FONT_MONO });
  return slide;
}

