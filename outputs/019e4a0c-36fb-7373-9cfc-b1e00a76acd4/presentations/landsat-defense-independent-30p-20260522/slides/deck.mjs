import fsSync from "node:fs";
import path from "node:path";

const W = 1280;
const H = 720;
const FONT = "Microsoft YaHei";
const MONO = "Aptos Mono";

const C = {
  red: "#8A1E2D",
  red2: "#B53A3D",
  ink: "#18324A",
  blue: "#315E88",
  teal: "#2B9E9B",
  green: "#5C8F47",
  gold: "#C3923E",
  paper: "#FAFAF7",
  panel: "#FFFFFF",
  soft: "#F1F3F5",
  line: "#D7DDE4",
  text: "#263747",
  muted: "#6B7887",
};

function repoRoot(ctx) {
  return path.resolve(ctx.workspaceDir, "..", "..", "..", "..");
}

function asset(ctx, ...parts) {
  return path.join(repoRoot(ctx), ...parts);
}

function workspaceAsset(ctx, fileName) {
  return path.join(ctx.workspaceDir, "assets", fileName);
}

function exists(p) {
  return Boolean(p) && fsSync.existsSync(p);
}

function ln(color, width = 1) {
  return { color, width, transparency: 0 };
}

function rect(slide, ctx, o) {
  return ctx.addShape(slide, o);
}

function tx(slide, ctx, o) {
  return ctx.addText(slide, {
    left: o.left,
    top: o.top,
    width: o.width,
    height: o.height,
    text: o.text,
    fontSize: o.size ?? 14,
    color: o.color ?? C.text,
    bold: o.bold ?? false,
    typeface: o.face ?? FONT,
    align: o.align ?? "left",
    valign: o.valign ?? "top",
    fill: o.fill ?? "#00000000",
    line: o.line ?? ln("#00000000", 0),
    insets: o.insets ?? { left: 0, right: 0, top: 0, bottom: 0 },
  });
}

async function img(slide, ctx, o) {
  if (!exists(o.path)) return null;
  return ctx.addImage(slide, o);
}

function seal(slide, ctx, { x, y, color = C.red, light = false }) {
  rect(slide, ctx, { left: x, top: y, width: 40, height: 40, geometry: "ellipse", fill: "#00000000", line: ln(light ? "#F7E8EA" : color, 1.2) });
  rect(slide, ctx, { left: x + 6, top: y + 6, width: 28, height: 28, geometry: "ellipse", fill: "#00000000", line: ln(light ? "#F7E8EA" : color, 0.8) });
  tx(slide, ctx, { left: x + 6, top: y + 10, width: 28, height: 14, text: "校", size: 12, color: light ? "#F7E8EA" : color, bold: true, align: "center" });
}

async function schoolSeal(slide, ctx, spec) {
  const p = workspaceAsset(ctx, "school-emblem.png");
  if (!exists(p)) return;
  const pos = spec.type === "cover"
    ? { left: 1126, top: 16, size: 54 }
    : spec.type === "section"
      ? { left: 1110, top: 34, size: 50 }
      : { left: 1148, top: 10, size: 46 };
  await img(slide, ctx, {
    left: pos.left,
    top: pos.top,
    width: pos.size,
    height: pos.size,
    path: p,
    fit: "contain",
    alt: "school emblem",
  });
}

function page(slide, ctx, spec) {
  rect(slide, ctx, { left: 0, top: 0, width: W, height: H, fill: C.paper, line: ln(C.paper, 0) });
  rect(slide, ctx, { left: 0, top: 0, width: 96, height: H, fill: C.ink, line: ln(C.ink, 0) });
  rect(slide, ctx, { left: 96, top: 0, width: W - 96, height: 62, fill: C.panel, line: ln(C.panel, 0) });
  rect(slide, ctx, { left: 96, top: 61, width: W - 138, height: 2, fill: C.red, line: ln(C.red, 0) });
  tx(slide, ctx, { left: 28, top: 34, width: 40, height: 20, text: String(spec.no).padStart(2, "0"), size: 16, color: "#FFFFFF", bold: true, align: "center", face: MONO });
  tx(slide, ctx, { left: 20, top: 95, width: 58, height: 230, text: spec.section ?? "毕业设计答辩", size: 11, color: "#E7EEF5", bold: true, align: "center" });
  tx(slide, ctx, { left: 124, top: 22, width: 850, height: 28, text: spec.title, size: 22, color: C.ink, bold: true });
  tx(slide, ctx, { left: 1018, top: 28, width: 120, height: 14, text: "毕业设计答辩", size: 9, color: C.muted, align: "right" });
  seal(slide, ctx, { x: 1154, y: 13, color: C.red });
  rect(slide, ctx, { left: 96, top: 688, width: W - 96, height: 32, fill: "#EEF1F4", line: ln("#EEF1F4", 0) });
  tx(slide, ctx, { left: 124, top: 699, width: 760, height: 10, text: spec.source ? `来源：${spec.source}` : "来源：项目 README、论文正文与源码", size: 7.6, color: C.muted });
  tx(slide, ctx, { left: 1165, top: 699, width: 40, height: 10, text: String(spec.no).padStart(2, "0"), size: 7.6, color: C.muted, align: "right", face: MONO });
}

function ribbon(slide, ctx, { x, y, w, text, color = C.red }) {
  rect(slide, ctx, { left: x, top: y, width: w, height: 26, fill: color, line: ln(color, 0) });
  tx(slide, ctx, { left: x + 10, top: y + 7, width: w - 20, height: 10, text, size: 9, color: "#FFFFFF", bold: true, align: "center" });
}

function box(slide, ctx, { x, y, w, h, title, body, color = C.red, fill = C.panel }) {
  rect(slide, ctx, { left: x, top: y, width: w, height: h, fill, line: ln(C.line, 1) });
  rect(slide, ctx, { left: x, top: y, width: 6, height: h, fill: color, line: ln(color, 0) });
  tx(slide, ctx, { left: x + 22, top: y + 16, width: w - 40, height: 20, text: title, size: 14, color: C.ink, bold: true });
  tx(slide, ctx, { left: x + 22, top: y + 46, width: w - 40, height: Math.max(12, h - 54), text: body, size: 11.2, color: C.text });
}

function bullets(slide, ctx, { x, y, w, items, color = C.red, size = 12, gap = 28 }) {
  items.forEach((item, i) => {
    const yy = y + i * gap;
    rect(slide, ctx, { left: x, top: yy + 7, width: 6, height: 6, geometry: "ellipse", fill: color, line: ln(color, 0) });
    tx(slide, ctx, { left: x + 18, top: yy, width: w - 18, height: gap, text: item, size, color: C.text });
  });
}

function stat(slide, ctx, { x, y, w, value, label, color = C.red }) {
  rect(slide, ctx, { left: x, top: y, width: w, height: 76, fill: C.panel, line: ln(C.line, 1) });
  tx(slide, ctx, { left: x, top: y + 12, width: w, height: 28, text: value, size: 24, color, bold: true, align: "center", face: MONO });
  tx(slide, ctx, { left: x + 10, top: y + 46, width: w - 20, height: 16, text: label, size: 9.5, color: C.muted, align: "center" });
}

function flow(slide, ctx, { x, y, steps, colors }) {
  steps.forEach((s, i) => {
    const xx = x + i * 202;
    rect(slide, ctx, { left: xx, top: y, width: 150, height: 86, fill: C.panel, line: ln(colors[i] ?? C.red, 1.5) });
    tx(slide, ctx, { left: xx + 15, top: y + 18, width: 120, height: 18, text: s[0], size: 14, color: C.ink, bold: true, align: "center" });
    tx(slide, ctx, { left: xx + 16, top: y + 46, width: 118, height: 24, text: s[1], size: 9.5, color: C.muted, align: "center" });
    if (i < steps.length - 1) {
      rect(slide, ctx, { left: xx + 158, top: y + 42, width: 34, height: 2, fill: C.red, line: ln(C.red, 0) });
      tx(slide, ctx, { left: xx + 188, top: y + 32, width: 18, height: 18, text: ">", size: 16, color: C.red, bold: true });
    }
  });
}

function table(slide, ctx, { x, y, widths, rows, rh = 46 }) {
  rows.forEach((row, r) => {
    let xx = x;
    row.forEach((cell, c) => {
      const fill = r === 0 ? "#EAEFF4" : C.panel;
      rect(slide, ctx, { left: xx, top: y + r * rh, width: widths[c], height: rh, fill, line: ln(C.line, 1) });
      tx(slide, ctx, { left: xx + 10, top: y + r * rh + 9, width: widths[c] - 20, height: rh - 12, text: cell, size: r === 0 ? 10.5 : 10, color: r === 0 ? C.ink : C.text, bold: r === 0, valign: "middle" });
      xx += widths[c];
    });
  });
}

function code(slide, ctx, { x, y, w, h, title, lines, color = C.red, highlights = [] }) {
  rect(slide, ctx, { left: x, top: y, width: w, height: h, fill: "#F7F8FA", line: ln(C.line, 1) });
  rect(slide, ctx, { left: x, top: y, width: w, height: 30, fill: C.ink, line: ln(C.ink, 0) });
  rect(slide, ctx, { left: x + 14, top: y + 9, width: 6, height: 12, fill: color, line: ln(color, 0) });
  tx(slide, ctx, { left: x + 30, top: y + 8, width: w - 40, height: 12, text: title, size: 9.5, color: "#FFFFFF", bold: true, face: MONO });
  highlights.forEach((item) => {
    const lineNo = typeof item === "number" ? item : item.line;
    const yy = y + 50 + (lineNo - 1) * 11.5;
    rect(slide, ctx, { left: x + 12, top: yy, width: 4, height: 12, fill: item.color ?? color, line: ln(item.color ?? color, 0) });
    rect(slide, ctx, { left: x + 18, top: yy - 1, width: w - 36, height: 14, fill: item.fill ?? "#FFF3D5", line: ln("#00000000", 0) });
  });
  tx(slide, ctx, { left: x + 18, top: y + 44, width: w - 36, height: h - 58, text: lines.join("\n"), size: 9.1, color: "#172A3A", face: MONO });
}

async function framed(slide, ctx, { x, y, w, h, title, path: p, fit = "contain", color = C.red }) {
  rect(slide, ctx, { left: x, top: y, width: w, height: h, fill: C.panel, line: ln(C.line, 1) });
  ribbon(slide, ctx, { x: x + 16, y: y + 14, w: Math.min(230, w - 32), text: title, color });
  await img(slide, ctx, { left: x + 16, top: y + 50, width: w - 32, height: h - 64, path: p, fit, alt: title });
}

function placeholder(slide, ctx, { x, y, w, h, title, note, color = C.gold }) {
  rect(slide, ctx, { left: x, top: y, width: w, height: h, fill: C.panel, line: ln(C.line, 1) });
  ribbon(slide, ctx, { x: x + 14, y: y + 14, w: w - 28, text: "真实截图预留位", color });
  rect(slide, ctx, { left: x + w / 2 - 28, top: y + 74, width: 56, height: 44, fill: "#00000000", line: ln(color, 2) });
  tx(slide, ctx, { left: x + 18, top: y + 140, width: w - 36, height: 24, text: title, size: 15, color: C.ink, bold: true, align: "center" });
  tx(slide, ctx, { left: x + 18, top: y + 170, width: w - 36, height: 32, text: note, size: 9.8, color: C.muted, align: "center" });
}

const deck = [
  { no: 1, type: "cover", title: "基于 Web 的 Landsat 8 遥感影像在线预处理系统" },
  { no: 2, type: "thesisMap", title: "答辩逻辑：为什么做、怎么做、做成什么" },
  { no: 3, type: "agenda", title: "目录" },
  { no: 4, type: "imageText", section: "选题背景", title: "研究背景：遥感影像预处理是后续分析的基础", image: ["docs", "thesis-prep", "materials", "研究背景与意义（优化版）.png"], blocks: [["应用需求持续增加", "Landsat 数据广泛用于植被、水体、城市扩张、农业和生态监测。"], ["预处理流程复杂", "辐射定标、大气校正、质量掩膜、裁剪、合成和指数计算之间存在连续依赖。"], ["Web 化具有现实意义", "把任务配置、状态反馈和结果预览统一到浏览器界面，可降低使用门槛。"]], source: "论文第1章；研究背景图" },
  { no: 5, type: "matrix", section: "选题背景", title: "现有痛点：工具分散、流程不连续、结果难回访", cells: [["数据入口分散", "本地数据、在线检索和产品级别差异需要统一入口。"], ["处理链不统一", "L1 与 L2 的计算逻辑不同，容易在工程实现中混用。"], ["批量复用困难", "多景处理如果依赖重复手动操作，效率和稳定性都受影响。"], ["结果管理薄弱", "输出文件如果只散落在目录中，不利于答辩演示和后续复查。"]], source: "README.md；论文第3章" },
  { no: 6, type: "section", section: "第一部分", title: "选题背景与需求分析", subtitle: "先说明系统要解决的真实问题，再界定目标与边界。", points: ["研究意义", "建设目标", "功能需求"] },
  { no: 7, type: "goals", section: "需求分析", title: "建设目标：形成本地化 Web 遥感预处理工作台", source: "README.md；论文第3章" },
  { no: 8, type: "table", section: "需求分析", title: "功能需求与系统响应", source: "论文第2-3章" },
  { no: 9, type: "stats", section: "需求分析", title: "系统边界：主处理面向 Landsat，下载模块适度扩展", source: "README.md" },
  { no: 10, type: "route", section: "技术路线", title: "技术路线：数据入口、处理执行、结果资产三段闭环", source: "README.md；论文第3章" },
  { no: 11, type: "section", section: "第二部分", title: "系统总体设计", subtitle: "这一部分回答系统怎么搭、模块怎么分、数据怎么流。", points: ["总体架构", "分层设计", "业务流程"] },
  { no: 12, type: "architecture", section: "总体设计", title: "总体架构：前端工作台、后端服务与核心处理分层", source: "系统总体架构图；README.md" },
  { no: 13, type: "layers", section: "总体设计", title: "前后端分层：界面交互与计算任务解耦", source: "frontend-vue；remote_sensing_tools/api" },
  { no: 14, type: "flow", section: "总体设计", title: "核心业务流程：从数据输入到结果回访", source: "论文第3章" },
  { no: 15, type: "twoTrack", section: "总体设计", title: "L1 / L2 双链路：同一平台适配不同产品级别", source: "core/processor.py；README.md" },
  { no: 16, type: "section", section: "第三部分", title: "详细实现与功能模块", subtitle: "把系统拆成可演示、可验证的功能模块。", points: ["单景处理", "批量流程", "下载与结果"] },
  { no: 17, type: "module", section: "模块实现", title: "单景预处理模块：参数配置、任务执行与结果预览", source: "README.md；前端组件" },
  { no: 18, type: "aoi", section: "模块实现", title: "AOI 空间交互：把地图选择转化为处理约束", source: "OpenLayers；论文第4章" },
  { no: 19, type: "batch", section: "模块实现", title: "批量流程模块：从可视化画布到批处理作业", source: "Vue Flow；services/graph_executor.py" },
  { no: 20, type: "download", section: "模块实现", title: "在线检索下载：STAC 检索、资产勾选与下载队列", source: "services/landsat_download.py" },
  { no: 21, type: "assetCenter", section: "模块实现", title: "结果资产中心：让输出结果可预览、可下载、可回访", source: "services/task_results.py" },
  { no: 22, type: "section", section: "第四部分", title: "关键代码与技术难点", subtitle: "用源码证据证明系统实现了真实处理链，而不是静态页面。", points: ["算法链路", "代码证据", "难点解决"] },
  { no: 23, type: "algorithm", section: "关键实现", title: "算法实现：辐射定标、大气校正与质量掩膜", source: "core/processor.py；operations" },
  { no: 24, type: "code1", section: "关键实现", title: "关键代码 1：L1 / L2 双链路与 6S 失败回退", source: "core/processor.py；core/processing_common.py" },
  { no: 25, type: "code2", section: "关键实现", title: "关键代码 2：流程图如何转换为批处理配置", source: "services/graph_executor.py" },
  { no: 26, type: "code3", section: "关键实现", title: "关键代码 3：在线下载与结果资产组织", source: "services/landsat_download.py；services/task_results.py" },
  { no: 27, type: "difficulty", section: "关键实现", title: "技术难点与解决方案", source: "README.md；论文第4章；源码" },
  { no: 28, type: "section", section: "第五部分", title: "系统展示、测试与总结", subtitle: "用真实界面、测试口径和结论完成答辩收束。", points: ["界面展示", "测试验证", "总结展望"] },
  { no: 29, type: "screens", section: "系统展示", title: "真实界面展示：Playwright 复现实机演示路径", source: "Playwright Chrome 实机截图；docs/thesis-prep/materials/screenshots" },
  { no: 30, type: "final", section: "总结", title: "测试结论、后续工作与答辩收束", source: "论文第5章；README.md" },
];

async function renderCover(slide, ctx) {
  await img(slide, ctx, { left: 0, top: 0, width: W, height: H, path: asset(ctx, "docs", "thesis-prep", "materials", "封面.png"), fit: "cover", alt: "cover" });
  rect(slide, ctx, { left: 0, top: 0, width: W, height: H, fill: "#F6F4EFCC", line: ln("#F6F4EF", 0) });
  rect(slide, ctx, { left: 0, top: 0, width: W, height: 86, fill: C.red, line: ln(C.red, 0) });
  tx(slide, ctx, { left: 84, top: 29, width: 520, height: 24, text: "毕业设计答辩", size: 18, color: "#FFFFFF", bold: true });
  seal(slide, ctx, { x: 1136, y: 22, color: C.red, light: true });
  rect(slide, ctx, { left: 86, top: 170, width: 650, height: 270, fill: "#FFFFFFF0", line: ln("#E3D7D9", 1) });
  await img(slide, ctx, {
    left: 84,
    top: 108,
    width: 430,
    height: 94,
    path: workspaceAsset(ctx, "school-logo-full.png"),
    fit: "contain",
    alt: "school logo",
  });
  tx(slide, ctx, { left: 126, top: 244, width: 560, height: 92, text: "基于 Web 的 Landsat 8\n遥感影像在线预处理系统", size: 31, color: C.ink, bold: true });
  tx(slide, ctx, { left: 128, top: 358, width: 540, height: 24, text: "Remote Sensing Image Online Preprocessing Platform", size: 13, color: C.muted });
  rect(slide, ctx, { left: 126, top: 408, width: 86, height: 4, fill: C.red, line: ln(C.red, 0) });
  rect(slide, ctx, { left: 760, top: 500, width: 330, height: 92, fill: "#FFFFFFEA", line: ln("#E3D7D9", 1) });
  tx(slide, ctx, { left: 790, top: 526, width: 270, height: 44, text: "答辩人：李旭东\n指导教师：待填写\n日期：2026 年 5 月", size: 12, color: C.ink, bold: true });
}

function renderThesisMap(slide, ctx, spec) {
  page(slide, ctx, spec);
  const steps = [["为什么做", "背景与需求"], ["怎么设计", "架构与流程"], ["怎么实现", "模块与代码"], ["怎么证明", "界面与测试"]];
  flow(slide, ctx, { x: 170, y: 178, steps, colors: [C.red, C.blue, C.teal, C.gold] });
  rect(slide, ctx, { left: 170, top: 342, width: 860, height: 106, fill: "#FFFFFF", line: ln(C.line, 1) });
  tx(slide, ctx, { left: 198, top: 372, width: 800, height: 38, text: "新版不沿用上一次版式，而是改成正式论文答辩的报告型页面：章节清楚、证据靠前、截图大、代码短。", size: 17, color: C.ink, bold: true });
  bullets(slide, ctx, { x: 198, y: 484, w: 820, items: ["每一页只承担一个讲述任务。", "真实截图和源码片段作为主要证明对象。", "下载页、结果页和典型输出保留后续替换位置。"], color: C.red, size: 12.6, gap: 30 });
}

function renderAgenda(slide, ctx, spec) {
  page(slide, ctx, spec);
  const items = ["选题背景与需求分析", "系统总体设计", "详细实现与功能模块", "关键代码与技术难点", "系统展示、测试与总结"];
  items.forEach((it, i) => {
    const y = 132 + i * 92;
    rect(slide, ctx, { left: 170, top: y, width: 70, height: 54, fill: i === 0 ? C.red : "#EEF1F4", line: ln(i === 0 ? C.red : C.line, 1) });
    tx(slide, ctx, { left: 170, top: y + 17, width: 70, height: 18, text: `0${i + 1}`, size: 16, color: i === 0 ? "#FFFFFF" : C.red, bold: true, align: "center", face: MONO });
    rect(slide, ctx, { left: 262, top: y, width: 780, height: 54, fill: "#FFFFFF", line: ln(C.line, 1) });
    tx(slide, ctx, { left: 286, top: y + 15, width: 500, height: 22, text: it, size: 17, color: C.ink, bold: true });
  });
}

function renderImageText(slide, ctx, spec) {
  page(slide, ctx, spec);
  framed(slide, ctx, { x: 130, y: 128, w: 500, h: 420, title: "研究背景图", path: asset(ctx, ...spec.image), color: C.red });
  spec.blocks.forEach((b, i) => box(slide, ctx, { x: 675, y: 132 + i * 128, w: 430, h: 92, title: b[0], body: b[1], color: [C.red, C.blue, C.teal][i] }));
}

function renderMatrix(slide, ctx, spec) {
  page(slide, ctx, spec);
  spec.cells.forEach((c, i) => {
    const x = 142 + (i % 2) * 480;
    const y = 150 + Math.floor(i / 2) * 180;
    box(slide, ctx, { x, y, w: 410, h: 120, title: c[0], body: c[1], color: [C.red, C.blue, C.teal, C.gold][i], fill: i % 2 ? "#FBFCFD" : "#FFFFFF" });
  });
  box(slide, ctx, { x: 142, y: 530, w: 890, h: 58, title: "设计判断", body: "系统要把数据、处理和结果组织成连续工作流，而不是只完成某一个算法环节。", color: C.red });
}

function renderSection(slide, ctx, spec) {
  rect(slide, ctx, { left: 0, top: 0, width: W, height: H, fill: C.red, line: ln(C.red, 0) });
  rect(slide, ctx, { left: 0, top: 0, width: 118, height: H, fill: "#6F1825", line: ln("#6F1825", 0) });
  seal(slide, ctx, { x: 1115, y: 38, color: C.red, light: true });
  tx(slide, ctx, { left: 72, top: 72, width: 38, height: 22, text: String(spec.no).padStart(2, "0"), size: 16, color: "#FFFFFF", bold: true, face: MONO });
  tx(slide, ctx, { left: 170, top: 156, width: 820, height: 54, text: spec.title, size: 34, color: "#FFFFFF", bold: true });
  tx(slide, ctx, { left: 172, top: 236, width: 720, height: 38, text: spec.subtitle, size: 18, color: "#F3DDE0" });
  spec.points.forEach((p, i) => {
    rect(slide, ctx, { left: 178 + i * 270, top: 370, width: 220, height: 88, fill: "#FFFFFF16", line: ln("#F7E8EA", 0.8) });
    tx(slide, ctx, { left: 198 + i * 270, top: 394, width: 50, height: 24, text: `0${i + 1}`, size: 21, color: "#F9C65C", bold: true, face: MONO });
    tx(slide, ctx, { left: 198 + i * 270, top: 430, width: 170, height: 20, text: p, size: 15, color: "#FFFFFF", bold: true });
  });
}

function renderGoals(slide, ctx, spec) {
  page(slide, ctx, spec);
  const g = [["单景预处理", "完成波段上传、产品级别识别、预处理和结果预览。"], ["批量流程", "把多景影像处理步骤组织成可执行流程。"], ["在线取数", "支持按 AOI 检索遥感影像并管理下载资产。"], ["结果管理", "让处理输出可分类、可预览、可下载、可回访。"]];
  g.forEach((item, i) => box(slide, ctx, { x: 142 + (i % 2) * 500, y: 136 + Math.floor(i / 2) * 168, w: 430, h: 112, title: item[0], body: item[1], color: [C.red, C.blue, C.teal, C.gold][i] }));
  stat(slide, ctx, { x: 152, y: 520, w: 132, value: "L1/L2", label: "产品链路", color: C.red });
  stat(slide, ctx, { x: 320, y: 520, w: 132, value: "QA", label: "质量控制", color: C.blue });
  stat(slide, ctx, { x: 488, y: 520, w: 132, value: "STAC", label: "在线检索", color: C.teal });
  stat(slide, ctx, { x: 656, y: 520, w: 132, value: "Flow", label: "流程编排", color: C.gold });
}

function renderNeedTable(slide, ctx, spec) {
  page(slide, ctx, spec);
  table(slide, ctx, { x: 132, y: 132, widths: [150, 410, 410], rh: 58, rows: [["需求类型", "具体需求", "系统响应"], ["单景处理", "上传波段、MTL、QA 文件并提交任务", "异步任务、状态反馈、结果预览"], ["批量处理", "多景数据按流程节点执行", "图结构解析、拓扑排序、任务配置生成"], ["在线下载", "按 AOI、时间、云量和传感器检索", "STAC 检索、资产勾选、下载队列"], ["结果管理", "结果需要分类、预览和下载", "task_manifest、文件扫描、路径安全"], ["工程运行", "本地部署且演示稳定", "FastAPI + Vue + 配置化运行"]] });
}

function renderStats(slide, ctx, spec) {
  page(slide, ctx, spec);
  const stats = [["L1/L2", "Landsat 产品级别"], ["13", "常用遥感指数"], ["3", "主要页面模块"], ["4", "核心能力链路"], ["QA", "质量掩膜控制"]];
  stats.forEach((s, i) => stat(slide, ctx, { x: 140 + i * 180, y: 144, w: 132, value: s[0], label: s[1], color: [C.red, C.blue, C.teal, C.green, C.gold][i] }));
  box(slide, ctx, { x: 142, y: 286, w: 440, h: 118, title: "主处理边界", body: "预处理主链聚焦 Landsat 8/9 的 L1/L2 处理、合成、指数计算和质量控制。", color: C.red });
  box(slide, ctx, { x: 632, y: 286, w: 440, h: 118, title: "下载扩展边界", body: "下载检索模块支持 Landsat 7/8/9 与 Sentinel-2，作为数据入口与资产管理补充。", color: C.teal });
  box(slide, ctx, { x: 142, y: 470, w: 930, h: 70, title: "真实性口径", body: "答辩中不虚构精度提升比例，重点展示真实功能链路、源码证据、界面截图和测试结论。", color: C.gold });
}

function renderRoute(slide, ctx, spec) {
  page(slide, ctx, spec);
  flow(slide, ctx, { x: 150, y: 188, steps: [["数据入口", "上传 / STAC"], ["处理链路", "L1 / L2"], ["任务编排", "异步 / 批量"], ["结果资产", "预览 / 下载"], ["测试验证", "功能闭环"]], colors: [C.red, C.blue, C.teal, C.green, C.gold] });
  box(slide, ctx, { x: 150, y: 376, w: 880, h: 100, title: "路线概括", body: "以 Web 工作台作为交互入口，以 FastAPI 服务组织任务，以核心处理器和服务模块承担计算、下载与结果管理。", color: C.red });
}

function renderArchitecture(slide, ctx, spec) {
  page(slide, ctx, spec);
  framed(slide, ctx, { x: 126, y: 128, w: 500, h: 420, title: "总体架构图", path: asset(ctx, "docs", "thesis-prep", "materials", "系统总体架构（重点优化）.png"), color: C.red });
  [["前端表现层", "Vue 3、Vite、OpenLayers、Vue Flow，负责界面配置与空间交互。"], ["接口服务层", "FastAPI 负责任务提交、状态查询、下载管理与文件访问。"], ["核心处理层", "完成定标、校正、掩膜、裁剪、合成与指数计算。"], ["数据资产层", "data、output、temp、cache 与清单文件支撑结果回访。"]].forEach((b, i) => box(slide, ctx, { x: 676, y: 130 + i * 100, w: 420, h: 76, title: b[0], body: b[1], color: [C.red, C.blue, C.teal, C.gold][i] }));
}

function renderLayers(slide, ctx, spec) {
  page(slide, ctx, spec);
  const layers = [["浏览器工作台", "参数配置\n地图交互\n流程画布"], ["FastAPI 接口", "上传校验\n任务提交\n状态查询"], ["服务模块", "图执行器\n下载服务\n结果扫描"], ["核心算法", "辐射定标\n质量掩膜\n指数合成"]];
  layers.forEach((l, i) => {
    rect(slide, ctx, { left: 142 + i * 235, top: 160, width: 180, height: 270, fill: "#FFFFFF", line: ln([C.red, C.blue, C.teal, C.gold][i], 1.5) });
    tx(slide, ctx, { left: 162 + i * 235, top: 190, width: 140, height: 28, text: l[0], size: 16, color: C.ink, bold: true, align: "center" });
    tx(slide, ctx, { left: 172 + i * 235, top: 264, width: 120, height: 96, text: l[1], size: 14, color: C.text, align: "center" });
    if (i < 3) tx(slide, ctx, { left: 326 + i * 235, top: 282, width: 30, height: 24, text: ">", size: 22, color: C.red, bold: true, align: "center" });
  });
  box(slide, ctx, { x: 142, y: 500, w: 880, h: 66, title: "设计收益", body: "前端专注交互，后端集中处理状态与文件安全，算法层保持独立，便于后续扩展。", color: C.red });
}

function renderCoreFlow(slide, ctx, spec) {
  page(slide, ctx, spec);
  flow(slide, ctx, { x: 138, y: 190, steps: [["输入数据", "波段 / MTL"], ["任务配置", "AOI / 参数"], ["处理执行", "算法链"], ["结果生成", "预览 / TIFF"], ["资产回访", "manifest"]], colors: [C.red, C.blue, C.teal, C.green, C.gold] });
  box(slide, ctx, { x: 138, y: 384, w: 880, h: 92, title: "闭环关键", body: "系统把参数、状态、结果和访问路径组织在一起，使任务结果能够被再次查看、下载和用于答辩展示。", color: C.gold });
}

function renderTwoTrack(slide, ctx, spec) {
  page(slide, ctx, spec);
  box(slide, ctx, { x: 142, y: 190, w: 180, h: 86, title: "影像输入", body: "波段文件\nMTL 元数据\nQA 文件", color: C.red });
  flow(slide, ctx, { x: 372, y: 138, steps: [["L1 产品", "DN / TOA"], ["大气校正", "Py6S / DOS"], ["L1 输出", "合成 / 指数"]], colors: [C.blue, C.teal, C.blue] });
  flow(slide, ctx, { x: 372, y: 340, steps: [["L2 产品", "缩放系数"], ["直接分析", "跳过校正"], ["L2 输出", "统一结构"]], colors: [C.green, C.green, C.green] });
  box(slide, ctx, { x: 142, y: 532, w: 880, h: 58, title: "质量控制贯穿全流程", body: "QA_PIXEL 与 QA_RADSAT 用于云、阴影、雪、卷云和饱和像元控制。", color: C.gold });
}

async function renderModule(slide, ctx, spec) {
  page(slide, ctx, spec);
  await framed(slide, ctx, { x: 126, y: 126, w: 620, h: 410, title: "Playwright 实机截图：单景处理", path: workspaceAsset(ctx, "pw-single.png"), fit: "cover", color: C.red });
  [["输入组织", "波段、MTL、QA 与 AOI 参数统一配置。"], ["异步提交", "前端提交任务，后端执行处理链并返回状态。"], ["步骤反馈", "进度、步骤状态与异常信息持续更新。"], ["结果预览", "输出路径、预览图和下载入口集中展示。"]].forEach((b, i) => box(slide, ctx, { x: 786, y: 126 + i * 102, w: 318, h: 78, title: b[0], body: b[1], color: [C.red, C.blue, C.teal, C.gold][i] }));
  box(slide, ctx, { x: 126, y: 562, w: 978, h: 44, title: "展示口径", body: "现场优先演示单景处理：配置输入、提交任务、查看状态、回访结果，形成一条最稳定的答辩演示链。", color: C.red });
}

async function renderAoi(slide, ctx, spec) {
  page(slide, ctx, spec);
  await framed(slide, ctx, { x: 132, y: 128, w: 610, h: 392, title: "真实截图：AOI 配置", path: asset(ctx, "docs", "thesis-prep", "materials", "screenshots", "ss-4-02-single-task-aoi-config.png"), fit: "cover", color: C.blue });
  [["交互输入", "地图框选、坐标输入或矢量文件导入。"], ["后端约束", "AOI 参数进入裁剪、检索和场景筛选流程。"], ["答辩证据", "AOI 配置与单景处理、影像下载两个模块共用同一空间约束。"]].forEach((b, i) => box(slide, ctx, { x: 790, y: 128 + i * 116, w: 318, h: 86, title: b[0], body: b[1], color: [C.red, C.blue, C.gold][i] }));
  box(slide, ctx, { x: 132, y: 548, w: 976, h: 48, title: "设计价值", body: "把地图交互转成可执行参数，避免只靠文件路径处理，使 Web 工作台具备更强的遥感业务表达能力。", color: C.teal });
}

async function renderBatch(slide, ctx, spec) {
  page(slide, ctx, spec);
  await framed(slide, ctx, { x: 126, y: 126, w: 640, h: 410, title: "Playwright 实机截图：批量流程画布", path: workspaceAsset(ctx, "pw-batch-click.png"), fit: "cover", color: C.teal });
  [["前端画布", "Vue Flow 负责节点展示、参数编辑和连接关系维护。"], ["图到任务", "后端将节点、连线和场景上下文转换为 BatchJobConfig。"], ["稳定执行", "先校验可达性与拓扑顺序，再提交批处理队列。"]].forEach((b, i) => box(slide, ctx, { x: 808, y: 132 + i * 122, w: 300, h: 92, title: b[0], body: b[1], color: [C.blue, C.teal, C.gold][i] }));
  box(slide, ctx, { x: 126, y: 562, w: 982, h: 44, title: "答辩讲法", body: "这一页证明批处理不是简单循环，而是把可视化流程图解释成有顺序、有约束、可批量复用的任务配置。", color: C.red });
}

async function renderDownload(slide, ctx, spec) {
  page(slide, ctx, spec);
  await framed(slide, ctx, { x: 126, y: 120, w: 675, h: 424, title: "Playwright 实机截图：影像下载", path: workspaceAsset(ctx, "pw-download-click.png"), fit: "cover", color: C.red });
  box(slide, ctx, { x: 832, y: 126, w: 276, h: 88, title: "STAC 检索", body: "支持 AOI、时间、云量、传感器和产品级别筛选。", color: C.red });
  box(slide, ctx, { x: 832, y: 242, w: 276, h: 88, title: "资产勾选", body: "按波段、元数据和质量文件选择下载资产。", color: C.blue });
  box(slide, ctx, { x: 832, y: 358, w: 276, h: 88, title: "下载队列", body: "服务端下载、代理配置、目录配置和失败重试统一管理。", color: C.teal });
  box(slide, ctx, { x: 126, y: 568, w: 982, h: 42, title: "截图来源", body: "Playwright + Chrome 从本机运行前端获取，右上角 API 在线状态用于证明前后端联通。", color: C.gold });
}

async function renderAssetCenter(slide, ctx, spec) {
  page(slide, ctx, spec);
  await framed(slide, ctx, { x: 126, y: 120, w: 690, h: 420, title: "Playwright 实机截图：结果资产中心", path: workspaceAsset(ctx, "pw-results.png"), fit: "cover", color: C.green });
  [["任务清单", "task_manifest 记录任务参数、路径和结果摘要。"], ["结果分类", "processed、composite、mask、metadata 等类别组织文件。"], ["安全访问", "通过安全路径和下载 URL 避免任意文件访问。"]].forEach((b, i) => box(slide, ctx, { x: 846, y: 126 + i * 120, w: 262, h: 88, title: b[0], body: b[1], color: [C.red, C.blue, C.teal][i] }));
  box(slide, ctx, { x: 126, y: 568, w: 982, h: 42, title: "模块价值", body: "结果中心把输出目录转化为可读的资产清单，答辩时可直接展示历史任务、产物数量、预览和下载入口。", color: C.gold });
}

function renderAlgorithm(slide, ctx, spec) {
  page(slide, ctx, spec);
  box(slide, ctx, { x: 132, y: 136, w: 330, h: 116, title: "L1 算法链", body: "DN 值转换、辐射定标、TOA 反射率、大气校正和指数计算。", color: C.red });
  box(slide, ctx, { x: 132, y: 278, w: 330, h: 116, title: "L2 分析链", body: "按官方缩放系数读取表面反射率，跳过重复辐射/大气预处理。", color: C.green });
  code(slide, ctx, { x: 510, y: 136, w: 560, h: 258, title: "processor.py / product-level decision", lines: ["product_level = self._normalize_product_level(product_level)", "if product_level == 'L2':", "    reflectance = self._load_l2_surface_reflectance(...)", "else:", "    radiance = self._dn_to_radiance(dn, metadata, band_name)", "    reflectance = self._radiance_to_toa_reflectance(...)", "    reflectance, method = self._apply_atmospheric_correction(...)", "valid_mask = build_quality_mask(qa_pixel, qa_radsat)"], color: C.red });
  box(slide, ctx, { x: 132, y: 486, w: 938, h: 62, title: "讲解重点", body: "不需要展开所有公式，重点说明系统如何在工程上处理产品级别差异和质量控制。", color: C.gold });
}

function renderCode1(slide, ctx, spec) {
  page(slide, ctx, spec);
  code(slide, ctx, { x: 132, y: 138, w: 470, h: 342, title: "processor.py / _apply_atmospheric_correction", lines: ["normalized_method = str(atm_correction_method or 'DOS').upper()", "if not apply_atm_correction or normalized_method in {'NONE','NO','SKIP'}:", "    return reflectance, 'NONE'", "if normalized_method != '6S':", "    corrected = dark_object_subtraction(reflectance)", "    return corrected, 'DOS'", "try:", "    corrected = self.sixs_atmospheric_correction(reflectance, band_name)", "    return corrected, '6S'", "except Exception as exc:", "    corrected = dark_object_subtraction(reflectance)", "    return corrected, 'DOS(6S fallback)'"], color: C.red, highlights: [{ line: 4, color: C.red }, { line: 10, color: C.gold }, { line: 12, color: C.gold }] });
  code(slide, ctx, { x: 642, y: 138, w: 430, h: 222, title: "processing_common.py / L2 scale", lines: ["PROCESSED_BAND_NODATA = -9999.0", "LANDSAT_L2_SR_SCALE = np.float32(0.0000275)", "LANDSAT_L2_SR_OFFSET = np.float32(-0.2)", "SENTINEL2_L2A_SR_SCALE = np.float32(0.0001)", "", "np.multiply(reflectance, LANDSAT_L2_SR_SCALE, out=reflectance)", "reflectance += LANDSAT_L2_SR_OFFSET", "reflectance[~valid_mask] = np.nan"], color: C.green, highlights: [{ line: 2, color: C.green }, { line: 3, color: C.green }, { line: 6, color: C.gold }, { line: 7, color: C.gold }] });
  box(slide, ctx, { x: 642, y: 402, w: 430, h: 78, title: "讲解重点", body: "L1 负责定标与校正；L2 采用官方缩放系数直接进入表面反射率分析。6S 不可用时回退 DOS，保证演示稳定。", color: C.gold });
}

function renderCode2(slide, ctx, spec) {
  page(slide, ctx, spec);
  code(slide, ctx, { x: 132, y: 136, w: 482, h: 326, title: "graph_executor.py / build_job_configs", lines: ["output_node = self._find_node(nodes, 'output')", "start_node = self._find_node(nodes, 'input')", "forward_reachable = self._reachable_nodes(start_node['id'], edges)", "backward_reachable = self._reverse_reachable_nodes(output_node['id'], edges)", "active_node_ids = forward_reachable & backward_reachable", "sorted_ids = self._topological_sort(active_nodes, active_edges)", "ctx = self._extract_context(sorted_ids, nodes, edges)", "errors.extend(self._validate_graph(ctx, sorted_nodes))", "configs = [self._build_single_config(scene, ctx) for scene in scenes]"], color: C.blue, highlights: [{ line: 3, color: C.blue }, { line: 4, color: C.blue }, { line: 6, color: C.teal }, { line: 8, color: C.gold }] });
  code(slide, ctx, { x: 654, y: 136, w: 418, h: 224, title: "Kahn topological sort", lines: ["in_degree: Dict[str, int] = defaultdict(int)", "queue = deque([node['id'] for node in nodes", "               if in_degree[node['id']] == 0])", "while queue:", "    node_id = queue.popleft()", "    result.append(node_id)", "    for nxt in adjacency[node_id]:", "        in_degree[nxt] -= 1", "        if in_degree[nxt] == 0: queue.append(nxt)"], color: C.teal, highlights: [{ line: 1, color: C.teal }, { line: 4, color: C.gold }, { line: 9, color: C.gold }] });
  box(slide, ctx, { x: 654, y: 404, w: 418, h: 72, title: "讲解重点", body: "可达性分析决定哪些节点真正参与任务；拓扑排序决定执行顺序；校验失败则阻止提交。", color: C.gold });
}

function renderCode3(slide, ctx, spec) {
  page(slide, ctx, spec);
  code(slide, ctx, { x: 132, y: 140, w: 470, h: 268, title: "landsat_download.py / product and download control", lines: ["PRODUCT_CONFIGS = {", "  'landsat': {'L2': {'collection': 'landsat-c2-l2'},", "              'L1': {'collection': 'landsat-c2l1'}},", "  'sentinel-2': {'L2A': {'collection': 'sentinel-2-l2a'}}", "}", "self._set_proxy_state(enabled=..., proxy_url=..., no_proxy=...)", "self._download_semaphore = asyncio.Semaphore(max_concurrent_downloads)", "async with self._download_semaphore:"], color: C.red, highlights: [{ line: 2, color: C.red }, { line: 4, color: C.blue }, { line: 7, color: C.gold }, { line: 8, color: C.gold }] });
  code(slide, ctx, { x: 642, y: 140, w: 430, h: 268, title: "task_results.py / result organization", lines: ["MANIFEST_FILENAME = 'task_manifest.json'", "PROCESSED_PATTERN = re.compile(...)", "if file_path.name == MANIFEST_FILENAME: return 'metadata'", "if PROCESSED_PATTERN.match(stem): return 'processed'", "if stem in COMPOSITE_NAMES: return 'composite'", "add_result_artifact(path_value, category='mask')", "download_url = build_safe_download_url(path)"], color: C.teal, highlights: [{ line: 1, color: C.teal }, { line: 4, color: C.green }, { line: 5, color: C.green }, { line: 7, color: C.gold }] });
  box(slide, ctx, { x: 132, y: 462, w: 940, h: 70, title: "讲解重点", body: "下载模块解决数据入口，结果模块解决输出回访。二者共同把“能处理”扩展为“能取数、能归档、能演示”。", color: C.gold });
}

function renderDifficulty(slide, ctx, spec) {
  page(slide, ctx, spec);
  table(slide, ctx, { x: 132, y: 132, widths: [190, 360, 360], rh: 70, rows: [["技术难点", "解决方案", "证明材料"], ["产品级别兼容", "L1 走定标和校正；L2 按缩放系数直用。", "processor.py、constants.py"], ["流程图执行", "可达性分析、拓扑排序、节点约束校验。", "graph_executor.py"], ["结果可回访", "task_manifest、分类扫描和安全下载路径。", "task_results.py"], ["演示稳定性", "异步任务、失败回退、下载重试和代理配置。", "README.md、服务模块"]] });
}

async function renderScreens(slide, ctx, spec) {
  page(slide, ctx, spec);
  await framed(slide, ctx, { x: 124, y: 112, w: 470, h: 292, title: "01 单景处理", path: workspaceAsset(ctx, "pw-single.png"), fit: "cover", color: C.red });
  await framed(slide, ctx, { x: 626, y: 112, w: 238, h: 160, title: "02 批量画布", path: workspaceAsset(ctx, "pw-batch-click.png"), fit: "cover", color: C.teal });
  await framed(slide, ctx, { x: 892, y: 112, w: 238, h: 160, title: "03 影像下载", path: workspaceAsset(ctx, "pw-download-click.png"), fit: "cover", color: C.gold });
  await framed(slide, ctx, { x: 626, y: 304, w: 238, h: 160, title: "04 结果中心", path: workspaceAsset(ctx, "pw-results.png"), fit: "cover", color: C.green });
  await framed(slide, ctx, { x: 892, y: 304, w: 238, h: 160, title: "05 AOI 配置", path: asset(ctx, "docs", "thesis-prep", "materials", "screenshots", "ss-4-02-single-task-aoi-config.png"), fit: "cover", color: C.blue });
  box(slide, ctx, { x: 124, y: 540, w: 1006, h: 54, title: "现场演示路线", body: "推荐顺序：单景处理验证主链路 → 批量画布说明工程扩展 → 影像下载说明数据入口 → 结果中心回访历史产物。", color: C.red });
}

function renderFinal(slide, ctx, spec) {
  page(slide, ctx, spec);
  table(slide, ctx, { x: 128, y: 132, widths: [150, 430, 130], rh: 52, rows: [["测试项", "验证内容", "现有结论"], ["单景预处理", "L1/L2、AOI 裁剪、合成、指数、状态轮询", "符合预期"], ["批量处理", "流程图校验、拓扑排序、任务配置生成", "符合预期"], ["在线下载", "AOI 检索、资产选择、代理与下载目录配置", "符合预期"], ["结果中心", "task_manifest 扫描、分类预览、下载访问", "符合预期"]] });
  box(slide, ctx, { x: 875, y: 132, w: 230, h: 112, title: "结论", body: "系统已形成可演示、可扩展的遥感影像在线预处理平台原型。", color: C.red });
  box(slide, ctx, { x: 875, y: 282, w: 230, h: 112, title: "后续工作", body: "补充处理时间统计、精度对比、用户权限和更多数据集验证。", color: C.gold });
  rect(slide, ctx, { left: 128, top: 560, width: 980, height: 76, fill: "#FFFFFF", line: ln(C.line, 1) });
  tx(slide, ctx, { left: 158, top: 586, width: 440, height: 26, text: "请各位老师批评指正", size: 24, color: C.ink, bold: true });
  tx(slide, ctx, { left: 876, top: 592, width: 190, height: 20, text: "THANK YOU", size: 18, color: C.red, bold: true, align: "right", face: MONO });
}

async function renderSpec(presentation, ctx, spec) {
  const slide = presentation.slides.add();
  if (spec.type === "cover") await renderCover(slide, ctx);
  else if (spec.type === "thesisMap") renderThesisMap(slide, ctx, spec);
  else if (spec.type === "agenda") renderAgenda(slide, ctx, spec);
  else if (spec.type === "imageText") await renderImageText(slide, ctx, spec);
  else if (spec.type === "matrix") renderMatrix(slide, ctx, spec);
  else if (spec.type === "section") renderSection(slide, ctx, spec);
  else if (spec.type === "goals") renderGoals(slide, ctx, spec);
  else if (spec.type === "table") renderNeedTable(slide, ctx, spec);
  else if (spec.type === "stats") renderStats(slide, ctx, spec);
  else if (spec.type === "route") renderRoute(slide, ctx, spec);
  else if (spec.type === "architecture") await renderArchitecture(slide, ctx, spec);
  else if (spec.type === "layers") renderLayers(slide, ctx, spec);
  else if (spec.type === "flow") renderCoreFlow(slide, ctx, spec);
  else if (spec.type === "twoTrack") renderTwoTrack(slide, ctx, spec);
  else if (spec.type === "module") await renderModule(slide, ctx, spec);
  else if (spec.type === "aoi") await renderAoi(slide, ctx, spec);
  else if (spec.type === "batch") await renderBatch(slide, ctx, spec);
  else if (spec.type === "download") await renderDownload(slide, ctx, spec);
  else if (spec.type === "assetCenter") await renderAssetCenter(slide, ctx, spec);
  else if (spec.type === "algorithm") renderAlgorithm(slide, ctx, spec);
  else if (spec.type === "code1") renderCode1(slide, ctx, spec);
  else if (spec.type === "code2") renderCode2(slide, ctx, spec);
  else if (spec.type === "code3") renderCode3(slide, ctx, spec);
  else if (spec.type === "difficulty") renderDifficulty(slide, ctx, spec);
  else if (spec.type === "screens") await renderScreens(slide, ctx, spec);
  else if (spec.type === "final") renderFinal(slide, ctx, spec);
  await schoolSeal(slide, ctx, spec);
  return slide;
}

export async function slide01(presentation, ctx) { return renderSpec(presentation, ctx, deck[0]); }
export async function slide02(presentation, ctx) { return renderSpec(presentation, ctx, deck[1]); }
export async function slide03(presentation, ctx) { return renderSpec(presentation, ctx, deck[2]); }
export async function slide04(presentation, ctx) { return renderSpec(presentation, ctx, deck[3]); }
export async function slide05(presentation, ctx) { return renderSpec(presentation, ctx, deck[4]); }
export async function slide06(presentation, ctx) { return renderSpec(presentation, ctx, deck[5]); }
export async function slide07(presentation, ctx) { return renderSpec(presentation, ctx, deck[6]); }
export async function slide08(presentation, ctx) { return renderSpec(presentation, ctx, deck[7]); }
export async function slide09(presentation, ctx) { return renderSpec(presentation, ctx, deck[8]); }
export async function slide10(presentation, ctx) { return renderSpec(presentation, ctx, deck[9]); }
export async function slide11(presentation, ctx) { return renderSpec(presentation, ctx, deck[10]); }
export async function slide12(presentation, ctx) { return renderSpec(presentation, ctx, deck[11]); }
export async function slide13(presentation, ctx) { return renderSpec(presentation, ctx, deck[12]); }
export async function slide14(presentation, ctx) { return renderSpec(presentation, ctx, deck[13]); }
export async function slide15(presentation, ctx) { return renderSpec(presentation, ctx, deck[14]); }
export async function slide16(presentation, ctx) { return renderSpec(presentation, ctx, deck[15]); }
export async function slide17(presentation, ctx) { return renderSpec(presentation, ctx, deck[16]); }
export async function slide18(presentation, ctx) { return renderSpec(presentation, ctx, deck[17]); }
export async function slide19(presentation, ctx) { return renderSpec(presentation, ctx, deck[18]); }
export async function slide20(presentation, ctx) { return renderSpec(presentation, ctx, deck[19]); }
export async function slide21(presentation, ctx) { return renderSpec(presentation, ctx, deck[20]); }
export async function slide22(presentation, ctx) { return renderSpec(presentation, ctx, deck[21]); }
export async function slide23(presentation, ctx) { return renderSpec(presentation, ctx, deck[22]); }
export async function slide24(presentation, ctx) { return renderSpec(presentation, ctx, deck[23]); }
export async function slide25(presentation, ctx) { return renderSpec(presentation, ctx, deck[24]); }
export async function slide26(presentation, ctx) { return renderSpec(presentation, ctx, deck[25]); }
export async function slide27(presentation, ctx) { return renderSpec(presentation, ctx, deck[26]); }
export async function slide28(presentation, ctx) { return renderSpec(presentation, ctx, deck[27]); }
export async function slide29(presentation, ctx) { return renderSpec(presentation, ctx, deck[28]); }
export async function slide30(presentation, ctx) { return renderSpec(presentation, ctx, deck[29]); }
