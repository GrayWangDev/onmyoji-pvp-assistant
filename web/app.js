const VERSION = "2026-05";
const STRATEGY_PATH = "../data/versions/2026-05/ban_magatsuhi/shijiamei/expert_a.json";

const state = {
  shikigami: [],
  builds: [],
  strategy: null,
  aliasToId: new Map(),
  shikigamiById: new Map(),
  buildsById: new Map(),
  ourBan: "ssrmagetsuhi",
  enemyBan: "",
  enemyPicks: [],
  query: "",
  screenshotImage: null,
  ocrRegionGroups: {
    left: {
      label: "我方名字牌",
      side: "our",
      regions: [
        { x: 0.10, y: 0.30, w: 0.28, h: 0.12, label: "我方桌面名字牌" },
        { x: 0.07, y: 0.23, w: 0.40, h: 0.25, label: "我方大范围" },
      ],
    },
    right: {
      label: "敌方名字牌",
      side: "enemy",
      regions: [
        { x: 0.49, y: 0.30, w: 0.30, h: 0.12, label: "敌方桌面名字牌" },
        { x: 0.48, y: 0.23, w: 0.42, h: 0.25, label: "敌方大范围" },
      ],
    },
  },
};

const els = {
  ourBanSelect: document.querySelector("#ourBanSelect"),
  enemyBanSelect: document.querySelector("#enemyBanSelect"),
  enemyPickedList: document.querySelector("#enemyPickedList"),
  shikigamiSearch: document.querySelector("#shikigamiSearch"),
  quickPickGrid: document.querySelector("#quickPickGrid"),
  results: document.querySelector("#results"),
  contextLine: document.querySelector("#contextLine"),
  matchCount: document.querySelector("#matchCount"),
  resetButton: document.querySelector("#resetButton"),
  screenshotInput: document.querySelector("#screenshotInput"),
  screenshotCanvas: document.querySelector("#screenshotCanvas"),
  ocrLeftButton: document.querySelector("#ocrLeftButton"),
  ocrRightButton: document.querySelector("#ocrRightButton"),
  ocrStatus: document.querySelector("#ocrStatus"),
  ocrResults: document.querySelector("#ocrResults"),
};

function normalize(value) {
  return String(value || "").trim().toLowerCase();
}

function resolveId(value) {
  const raw = String(value || "").trim();
  return state.aliasToId.get(raw) || state.aliasToId.get(normalize(raw)) || raw;
}

function resolveOcrText(text) {
  const raw = String(text || "").trim();
  const compact = raw.replace(/[^a-zA-Z0-9\u4e00-\u9fa5]/g, "");
  const candidates = [raw, compact, raw.toLowerCase(), compact.toLowerCase()];

  for (const candidate of candidates) {
    const id = state.aliasToId.get(candidate);
    if (id) return id;
  }

  const haystack = compact.toLowerCase();
  const fuzzyNames = state.shikigami
    .flatMap((item) => [item.id, item.name, ...(item.aliases || [])].map((name) => ({ id: item.id, name: String(name) })))
    .filter(({ name }) => name.replace(/[^a-zA-Z0-9\u4e00-\u9fa5]/g, "").length >= 5)
    .sort((a, b) => b.name.length - a.name.length);

  for (const { id, name } of fuzzyNames) {
    const needle = name.replace(/[^a-zA-Z0-9\u4e00-\u9fa5]/g, "").toLowerCase();
    if (needle && haystack.includes(needle)) {
      return id;
    }
  }

  return "";
}

function nameOf(id) {
  return state.shikigamiById.get(id)?.name || id;
}

function buildLabel(id) {
  const build = state.buildsById.get(id);
  if (!build) return id;
  return `${nameOf(build.shikigami_id)} · ${build.label}`;
}

function formatNames(ids) {
  return ids?.length ? ids.map(nameOf).join(" / ") : "无";
}

function bannedIds() {
  return new Set([state.ourBan, state.enemyBan].filter(Boolean));
}

function isBanned(id) {
  return bannedIds().has(id);
}

function removeBannedEnemyPicks() {
  const banned = bannedIds();
  const before = state.enemyPicks.length;
  state.enemyPicks = state.enemyPicks.filter((id) => !banned.has(id));
  return before !== state.enemyPicks.length;
}

function unavailablePicks(ids = []) {
  const banned = bannedIds();
  return ids.filter((id) => banned.has(id));
}

function enemyBansFor(matchup) {
  if (Array.isArray(matchup.enemy_bans)) return matchup.enemy_bans;
  if (matchup.enemy_ban) return [matchup.enemy_ban];
  return [];
}

function includesAll(selected, required = []) {
  return required.every((item) => selected.has(item));
}

function intersects(selected, candidates = []) {
  return candidates.some((item) => selected.has(item));
}

function systemScore(system, enemyPicks) {
  let score = Number(system.initial_score || 0);
  const confirmHits = system.confirm_picks?.filter((id) => enemyPicks.has(id)) || [];
  const fuzzyHits = system.fuzzy_picks?.filter((id) => enemyPicks.has(id)) || [];
  const excludedHits = system.excluded_picks?.filter((id) => enemyPicks.has(id)) || [];
  score += confirmHits.length * 50;
  score += fuzzyHits.length * 15;
  score -= excludedHits.length * 80;
  return { score, confirmHits, fuzzyHits, excludedHits };
}

function lineupMatches(lineup, enemyPicks) {
  if (lineup.enemy_opening && !includesAll(enemyPicks, lineup.enemy_opening)) return false;
  if (lineup.enemy_opening_contains && !includesAll(enemyPicks, lineup.enemy_opening_contains)) return false;
  return true;
}

function matchingBranches(lineup, enemyPicks, enemyPickOrder) {
  return (lineup.fifth_pick_branches || []).filter((branch) => {
    if (branch.enemy_picks_contains && !includesAll(enemyPicks, branch.enemy_picks_contains)) return false;
    if (branch.enemy_picks_excludes && intersects(enemyPicks, branch.enemy_picks_excludes)) return false;
    if (branch.enemy_pick_at) {
      return Object.entries(branch.enemy_pick_at).every(([slot, expected]) => {
        return enemyPickOrder[Number(slot) - 1] === expected;
      });
    }
    return true;
  });
}

function createOption(item) {
  const option = document.createElement("option");
  option.value = item.id;
  option.textContent = item.name;
  return option;
}

function renderSelects() {
  const sorted = [...state.shikigami].sort((a, b) => a.name.localeCompare(b.name, "zh-Hans-CN"));
  els.ourBanSelect.replaceChildren(...sorted.map(createOption));
  els.enemyBanSelect.replaceChildren(createOption({ id: "", name: "请选择" }), ...sorted.map(createOption));
  els.ourBanSelect.value = state.ourBan;
  els.enemyBanSelect.value = state.enemyBan;
}

function renderPicked() {
  if (!state.enemyPicks.length) {
    const empty = document.createElement("span");
    empty.className = "empty-inline";
    empty.textContent = "还没有添加敌方式神";
    els.enemyPickedList.replaceChildren(empty);
    return;
  }

  const nodes = state.enemyPicks.map((id, index) => {
    const pill = document.createElement("span");
    pill.className = "pill";
    pill.textContent = `${index + 1}. ${nameOf(id)}`;
    const button = document.createElement("button");
    button.type = "button";
    button.title = `移除 ${nameOf(id)}`;
    button.textContent = "×";
    button.addEventListener("click", () => {
      state.enemyPicks.splice(index, 1);
      render();
    });
    pill.append(button);
    return pill;
  });
  els.enemyPickedList.replaceChildren(...nodes);
}

function addEnemyPick(id) {
  if (!id || state.enemyPicks.includes(id)) return;
  if (isBanned(id)) return;
  state.enemyPicks.push(id);
  state.query = "";
  els.shikigamiSearch.value = "";
  render();
}

function renderQuickPicks() {
  const query = normalize(state.query);
  const filtered = state.shikigami
    .filter((item) => {
      if (!query) return true;
      const haystack = [item.id, item.name, ...(item.aliases || [])].map(normalize).join(" ");
      return haystack.includes(query);
    })
    .sort((a, b) => a.name.localeCompare(b.name, "zh-Hans-CN"))
    .slice(0, 60);

  const nodes = filtered.map((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "pick-button";
    button.textContent = isBanned(item.id) ? `${item.name} · 已ban` : item.name;
    button.disabled = state.enemyPicks.includes(item.id) || isBanned(item.id);
    button.addEventListener("click", () => addEnemyPick(item.id));
    return button;
  });
  els.quickPickGrid.replaceChildren(...nodes);
}

function drawScreenshotPreview(activeRegionKey = "") {
  if (!state.screenshotImage) return;

  const canvas = els.screenshotCanvas;
  const ctx = canvas.getContext("2d");
  const image = state.screenshotImage;
  const maxWidth = 760;
  const scale = Math.min(1, maxWidth / image.naturalWidth);
  canvas.width = Math.round(image.naturalWidth * scale);
  canvas.height = Math.round(image.naturalHeight * scale);

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height);

  for (const [key, group] of Object.entries(state.ocrRegionGroups)) {
    for (const region of group.regions) {
      const isActive = key === activeRegionKey;
      ctx.save();
      ctx.strokeStyle = isActive ? "#b42318" : "#2d6cdf";
      ctx.lineWidth = isActive ? 3 : 2;
      ctx.setLineDash(isActive ? [] : [6, 4]);
      ctx.strokeRect(region.x * canvas.width, region.y * canvas.height, region.w * canvas.width, region.h * canvas.height);
      ctx.restore();
    }
  }

  canvas.classList.add("is-visible");
}

function cropRegion(region) {
  const image = state.screenshotImage;
  if (!image || !region) return null;

  const canvas = document.createElement("canvas");
  const padding = 0.01;
  const sx = Math.max(0, (region.x - padding) * image.naturalWidth);
  const sy = Math.max(0, (region.y - padding) * image.naturalHeight);
  const sw = Math.min(image.naturalWidth - sx, (region.w + padding * 2) * image.naturalWidth);
  const sh = Math.min(image.naturalHeight - sy, (region.h + padding * 2) * image.naturalHeight);
  const scale = 3;
  canvas.width = Math.round(sw * scale);
  canvas.height = Math.round(sh * scale);

  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(image, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
  return canvas;
}

function truncateText(text, maxLength = 72) {
  if (!text) return "无文本";
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

function renderOcrCandidate({ regionLabel, text, id, side }) {
  const row = document.createElement("div");
  row.className = "ocr-result";

  const detail = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = id ? `${regionLabel}: ${nameOf(id)}` : `${regionLabel}: 未匹配`;
  const raw = document.createElement("p");
  raw.textContent = id ? `命中：${nameOf(id)} · OCR: ${truncateText(text)}` : `OCR: ${truncateText(text)}`;
  raw.title = text || "";
  detail.append(title, raw);

  const button = document.createElement("button");
  button.type = "button";
  button.className = "pick-button";
  if (side === "enemy") {
    button.textContent = id ? "加入" : "手动";
    button.disabled = !id || isBanned(id) || state.enemyPicks.includes(id);
    button.addEventListener("click", () => addEnemyPick(id));
  } else {
    button.textContent = "我方";
    button.disabled = true;
    button.title = "左侧是我方展示，暂不加入敌方已选。";
  }

  row.append(detail, button);
  els.ocrResults.prepend(row);
}

async function recognizeRegion(regionKey) {
  if (!state.screenshotImage) {
    els.ocrStatus.textContent = "请先上传一张 BP 截图。";
    return;
  }

  if (!window.Tesseract) {
    els.ocrStatus.textContent = "OCR 库加载失败，请检查网络后刷新页面。";
    return;
  }

  const group = state.ocrRegionGroups[regionKey];
  drawScreenshotPreview(regionKey);
  els.ocrStatus.textContent = `正在识别${group.label}...`;

  try {
    const attempts = [];
    for (const region of group.regions) {
      const crop = cropRegion(region);
      const result = await window.Tesseract.recognize(crop, "eng");
      const text = result.data.text.replace(/\s+/g, " ").trim();
      const id = resolveOcrText(text);
      const confidence = result.data.confidence || 0;
      attempts.push({ region, text, id, confidence });
      if (id) break;
    }

    const matched = attempts.find((attempt) => attempt.id);
    const best = matched || attempts.sort((a, b) => b.confidence - a.confidence)[0];
    const text = best?.text || "";
    const id = best?.id || "";
    els.ocrStatus.textContent = id ? `识别到 ${nameOf(id)}。` : "OCR 完成，但没有匹配到式神；可以继续手动输入。";
    renderOcrCandidate({ regionLabel: best?.region.label || group.label, text, id, side: group.side });
  } catch (error) {
    console.error(error);
    els.ocrStatus.textContent = `识别失败：${error.message}`;
  }
}

function renderDefaultRecommendation(defaultRec) {
  if (!defaultRec) return null;
  const box = document.createElement("div");
  box.className = "lineup";
  const unavailable = unavailablePicks(defaultRec.first_picks || []);
  box.innerHTML = `
    <div class="lineup-title">
      <h3>${defaultRec.name}</h3>
      <span class="tag">默认起手</span>
      ${unavailable.length ? `<span class="tag danger">含已ban</span>` : ""}
    </div>
    <p><span class="label">先选</span> ${formatNames(defaultRec.first_picks || [])}</p>
    ${unavailable.length ? `<p class="warning-text">不可用：${formatNames(unavailable)} 已被ban，需要改走替代方案或继续观察。</p>` : ""}
    ${defaultRec.first_builds?.length ? `<p><span class="label">配置</span> ${defaultRec.first_builds.map(buildLabel).join(" / ")}</p>` : ""}
    <p>${defaultRec.reason || ""}</p>
  `;
  return box;
}

function renderLineup(lineup, enemyPicks, enemyPickOrder) {
  const box = document.createElement("div");
  box.className = "lineup";
  const unavailable = unavailablePicks(lineup.picks || []);

  const tags = [...(lineup.style || []), lineup.risk_level ? `风险${lineup.risk_level}` : "", lineup.difficulty ? `难度${lineup.difficulty}` : ""]
    .filter(Boolean)
    .map((tag) => `<span class="tag">${tag}</span>`)
    .join("");

  const branches = matchingBranches(lineup, enemyPicks, enemyPickOrder);
  const branchHtml = branches.length
    ? `<div class="branch-list">${branches
        .map(
          (branch) => `
            <div class="branch">
              <p><span class="label">分支</span> ${formatNames(branch.next_picks || [])}</p>
              <p>${branch.reason || ""}</p>
            </div>
          `,
        )
        .join("")}</div>`
    : "";

  const fifthOptions = lineup.fifth_options?.length
    ? `<p><span class="label">5手可选</span> ${formatNames(lineup.fifth_options)}</p>`
    : "";

  const slotHtml = lineup.lineup_slots?.length
    ? lineup.lineup_slots
        .map(
          (slot) => `
            <p><span class="label">${slot.slot}手可选</span> ${formatNames(slot.options || [])}</p>
            ${slot.note ? `<p>${slot.note}</p>` : ""}
          `,
        )
        .join("")
    : "";

  box.innerHTML = `
    <div class="lineup-title">
      <h3>${lineup.name}</h3>
      ${tags}
      ${unavailable.length ? `<span class="tag danger">含已ban</span>` : ""}
    </div>
    <p><span class="label">阵容</span> ${formatNames(lineup.picks || [])}</p>
    ${unavailable.length ? `<p class="warning-text">不可用：${formatNames(unavailable)} 已被ban，这套阵容只能作为思路参考。</p>` : ""}
    ${lineup.builds?.length ? `<p><span class="label">配置</span> ${lineup.builds.map(buildLabel).join(" / ")}</p>` : ""}
    ${fifthOptions}
    ${slotHtml}
    <p>${lineup.reason || ""}</p>
    ${branchHtml}
  `;
  return box;
}

function renderSystem(system, scoreData, enemyPicks, enemyPickOrder) {
  const box = document.createElement("div");
  box.className = "system";

  const signal = scoreData.confirmHits.length
    ? `确认信号：${formatNames(scoreData.confirmHits)}`
    : scoreData.fuzzyHits.length
      ? `模糊信号：${formatNames(scoreData.fuzzyHits)}`
      : enemyPicks.size
        ? "还未命中明确信号"
        : "只根据 ban 位预测";

  const lineups = (system.recommended_lineups || []).filter((lineup) => !enemyPicks.size || lineupMatches(lineup, enemyPicks));

  const children = [
    htmlToNode(`
      <div class="system-title">
        <div>
          <h3>${system.name}</h3>
          <p>${signal}</p>
        </div>
        <span class="score">${scoreData.score}</span>
      </div>
    `),
  ];

  if (system.notes) {
    children.push(htmlToNode(`<p>${system.notes}</p>`));
  }

  if (lineups.length) {
    children.push(...lineups.map((lineup) => renderLineup(lineup, enemyPicks, enemyPickOrder)));
  } else {
    children.push(htmlToNode(`<div class="empty-state">暂无完全命中的推荐阵容，继续观察对方后续选择。</div>`));
  }

  box.replaceChildren(...children);
  return box;
}

function htmlToNode(html) {
  const template = document.createElement("template");
  template.innerHTML = html.trim();
  return template.content.firstElementChild;
}

function getMatches() {
  if (!state.strategy || !state.ourBan || !state.enemyBan) return [];
  const enemyPickOrder = [...state.enemyPicks];
  const enemyPicks = new Set(enemyPickOrder);

  return (state.strategy.matchups || [])
    .filter((matchup) => enemyBansFor(matchup).includes(state.enemyBan))
    .map((matchup) => {
      const systems = (matchup.enemy_systems || [])
        .map((system) => {
          const scoreData = systemScore(system, enemyPicks);
          const hasCoreHit = intersects(enemyPicks, system.core_picks || []);
          if (scoreData.excludedHits.length) return null;
          if (enemyPicks.size && !scoreData.confirmHits.length && !scoreData.fuzzyHits.length && !hasCoreHit) return null;
          if (scoreData.score <= 0) return null;
          return { system, scoreData };
        })
        .filter(Boolean)
        .sort((a, b) => b.scoreData.score - a.scoreData.score);
      return { matchup, systems, enemyPicks, enemyPickOrder };
    });
}

function renderResults() {
  removeBannedEnemyPicks();
  const matches = getMatches();
  els.contextLine.textContent = `${nameOf(state.ourBan)} vs ${state.enemyBan ? nameOf(state.enemyBan) : "未选择"} · 敌方 ${state.enemyPicks.length} 手`;
  els.matchCount.textContent = String(matches.length);

  if (!state.enemyBan) {
    els.results.replaceChildren(htmlToNode(`<div class="empty-state">先选择敌方 ban 位。</div>`));
    return;
  }

  if (!matches.length) {
    els.results.replaceChildren(
      htmlToNode(`
        <div class="empty-state">
          没有找到匹配策略包。当前可能是这个ban位还没录入，或对方选人不符合已有体系；先按经验手动判断，并把这个局面记录下来后续补规则。
        </div>
      `),
    );
    return;
  }

  const nodes = matches.map(({ matchup, systems, enemyPicks, enemyPickOrder }) => {
    const box = document.createElement("article");
    box.className = "matchup";
    const header = htmlToNode(`
      <div class="matchup-header">
        <div>
          <h3>${matchup.title}</h3>
          <p>${matchup.ambiguous_policy?.message || ""}</p>
        </div>
      </div>
    `);

    const children = [header];
    const defaultNode = renderDefaultRecommendation(matchup.default_recommendation);
    if (defaultNode) children.push(defaultNode);

    if (systems.length) {
      children.push(...systems.map(({ system, scoreData }) => renderSystem(system, scoreData, enemyPicks, enemyPickOrder)));
    } else if (matchup.ambiguous_policy?.message) {
      children.push(htmlToNode(`<div class="system"><div class="empty-state">${matchup.ambiguous_policy.message}</div></div>`));
    }

    box.replaceChildren(...children);
    return box;
  });

  els.results.replaceChildren(...nodes);
}

function render() {
  renderPicked();
  renderQuickPicks();
  renderResults();
}

function bindEvents() {
  els.ourBanSelect.addEventListener("change", () => {
    state.ourBan = els.ourBanSelect.value;
    removeBannedEnemyPicks();
    render();
  });

  els.enemyBanSelect.addEventListener("change", () => {
    state.enemyBan = els.enemyBanSelect.value;
    removeBannedEnemyPicks();
    render();
  });

  els.shikigamiSearch.addEventListener("input", () => {
    state.query = els.shikigamiSearch.value;
    renderQuickPicks();
  });

  els.shikigamiSearch.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const id = resolveId(els.shikigamiSearch.value);
    if (state.shikigamiById.has(id)) addEnemyPick(id);
  });

  els.screenshotInput.addEventListener("change", () => {
    const file = els.screenshotInput.files?.[0];
    if (!file) return;

    const image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(image.src);
      state.screenshotImage = image;
      els.ocrResults.replaceChildren();
      els.ocrStatus.textContent = "截图已加载。左侧是我方展示，右侧是敌方展示；当前 OCR 只识别中间名字牌。";
      drawScreenshotPreview();
    };
    image.src = URL.createObjectURL(file);
  });

  els.ocrLeftButton.addEventListener("click", () => recognizeRegion("left"));
  els.ocrRightButton.addEventListener("click", () => recognizeRegion("right"));

  els.resetButton.addEventListener("click", () => {
    state.enemyPicks = [];
    state.enemyBan = "";
    state.query = "";
    els.enemyBanSelect.value = "";
    els.shikigamiSearch.value = "";
    render();
  });
}

async function init() {
  const [shikigami, builds, strategy] = await Promise.all([
    fetch("../data/shikigami.json").then((res) => res.json()),
    fetch("../data/builds.json").then((res) => res.json()),
    fetch(STRATEGY_PATH).then((res) => res.json()),
  ]);

  state.shikigami = shikigami;
  state.builds = builds;
  state.strategy = strategy;
  state.shikigamiById = new Map(shikigami.map((item) => [item.id, item]));
  state.buildsById = new Map(builds.map((item) => [item.id, item]));

  for (const item of shikigami) {
    for (const alias of [item.id, item.name, ...(item.aliases || [])]) {
      state.aliasToId.set(alias, item.id);
      state.aliasToId.set(normalize(alias), item.id);
    }
  }

  renderSelects();
  bindEvents();
  render();
}

init().catch((error) => {
  console.error(error);
  els.results.replaceChildren(htmlToNode(`<div class="empty-state">加载数据失败：${error.message}</div>`));
});
