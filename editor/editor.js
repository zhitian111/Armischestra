import { deploymentGuide } from "./deployment.js";
import { marker, printStage } from "./print.js";

import {
  healthAt,
  inHealthBar,
  layoutTokens,
  updateHealthReferences,
} from "./health.js";

const $ = (s) => document.querySelector(s);
const paths = {
  open: "M3 17V5h6l2 2h10v3M2 19l3-8h17l-3 8z",
  save: "M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5",
  print: "M6 8V3h12v5M6 17H3v-7h18v7h-3M6 14h12v7H6zM17 12h1",
  clapper: "M3 10h18v10H3zM3 10l-1-5 17-3 1 5zM7 4l3 4m3-5 3 4",
  stage: "M3 4h18v14H3zM8 22l4-4 4 4",
  sliders: "M4 6h7m4 0h5M4 12h2m4 0h10M4 18h10m4 0h2M11 3v6m-5 0v6m8 0v6",
  sequence: "M3 5h4v4H3zM3 15h4v4H3zM11 7h10M11 17h10",
  plus: "M12 5v14M5 12h14",
  cross: "M12 2v5m0 10v5M2 12h5m10 0h5M7 7h10v10H7z",
  play: "M7 4l13 8-13 8z",
  pause: "M7 4v16m10-16v16",
  pencil: "M4 16 16 4l4 4L8 20l-5 1zM13 7l4 4",
  undo: "M9 5 4 10l5 5M4 10h9a6 6 0 0 1 1 12",
  redo: "m15 5 5 5-5 5m5-5h-9a6 6 0 0 0-1 12",
  close: "M5 5l14 14m0-14L5 19",
  up: "m5 15 7-7 7 7",
  down: "m5 9 7 7 7-7",
  trash: "M4 6h16M8 6V3h8v3M6 6l1 15h10l1-15m-8 4v7m4-7v7",
  arrow: "m9 5 7 7-7 7",
  image: "M3 3h18v18H3zM4 17l5-6 4 4 3-3 5 6M15 7h1",
  target: "M3 12h5m8 0h5M12 3v5m0 8v5M7 12a5 5 0 1 0 10 0 5 5 0 1 0-10 0",
};
const esc = (x) =>
  String(x).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const icon = (k) =>
  '<i data-icon="' +
  k +
  '"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="' +
  paths[k] +
  '"/></svg></i>';
document
  .querySelectorAll("i[data-icon]")
  .forEach((i) => (i.outerHTML = icon(i.dataset.icon)));
const clone = (o) => structuredClone(o);
const nfmt = (n) => Number(n.toFixed(2));
const xyLabel = (p) => p.map(nfmt).join(", ");
const isPush = (step) => step.op === "move" && step.method === "push";
const actionName = (step) =>
  isPush(step) ? "平推" : { move: "吸移", wait: "等待", cue: "字幕" }[step.op];
const cardKind = (card) => (card.kind === "prop" ? "道具" : "角色");
let project,
  actorName,
  stepIndex = 0,
  tab = "actors",
  pick = null,
  drag = null;
let preview = null,
  playing = false,
  previewMode = false,
  t = 0,
  last = 0,
  raf = 0,
  revision = 0;
let past = [],
  future = [],
  images = new Map(),
  geometry,
  toastTimer,
  submitting = false;
const board = $("#board"),
  ctx = board.getContext("2d");
function status(message) {
  const e = $("#status");
  e.textContent = message;
  e.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (e.hidden = true), 4500);
}
async function api(path, value) {
  const response = await fetch(
    path,
    value === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(value),
        },
  );
  const result = await response.json();
  if (!response.ok) throw Error(result.error || "请求未完成");
  return result;
}
function pause() {
  playing = false;
  cancelAnimationFrame(raf);
  updateControls();
}
function editMode() {
  pause();
  previewMode = false;
  t = 0;
  updateControls();
}
function remember() {
  past.push(clone(project));
  if (past.length > 25) past.shift();
  future = [];
}
function changed() {
  revision++;
  preview = null;
  editMode();
  pick = null;
  render();
}
function edit(fn) {
  remember();
  fn();
  changed();
}
function fixSelection() {
  let names = Object.keys(project.stage.actors);
  if (!Object.hasOwn(project.stage.actors, actorName)) actorName = names[0];
  stepIndex = Math.min(Math.max(stepIndex, 0), project.show.steps.length - 1);
}
function recover(from, to) {
  if (!from.length) return;
  to.push(project);
  project = from.pop();
  fixSelection();
  changed();
}
function thumb(a, name) {
  return (
    '<span class="thumb">' +
    (a.image
      ? '<img alt="" src="' + esc(a.image) + '">'
      : esc([...name][0] || "角")) +
    "</span>"
  );
}
function field(title, input) {
  return '<label class="field"><span>' + title + "</span>" + input + "</label>";
}
function num(id, value, min = null) {
  return (
    '<input id="' +
    id +
    '" type="number" step="any" required value="' +
    esc(value) +
    '"' +
    (min == null ? "" : ' min="' + min + '"') +
    ">"
  );
}
function coordinateFields(label, key, point, selectable = false) {
  return (
    '<div class="field"><span>' +
    label +
    '</span><div class="coordinates"><label>X ' +
    num(key + "X", point[0]) +
    "</label><label>Y " +
    num(key + "Y", point[1]) +
    "</label>" +
    (selectable
      ? '<button type="button" data-pick="' +
        key +
        '" aria-label="在棋盘上选择' +
        label +
        '" title="在棋盘上选择' +
        label +
        '">' +
        icon("target") +
        "</button>"
      : "") +
    "</div></div>"
  );
}
function v(id) {
  const elem = $("#" + id);
  if (!elem.reportValidity()) throw Error("请检查数值");
  return elem.valueAsNumber;
}
const pair = (id) => [v(id + "X"), v(id + "Y")];
function checkStagePoint(p) {
  const [w, h] = project.stage.size_mm;
  if (!(p[0] >= 0 && p[1] >= 0 && p[0] <= w && p[1] <= h))
    throw Error("坐标超出棋盘范围");
}
function render() {
  if (!project) return;
  fixSelection();
  $("#title").textContent = project.show.title;
  $("#undo").disabled = !past.length;
  $("#redo").disabled = !future.length;
  renderSide();
  renderSequence();
  renderStep();
  updateControls();
  draw();
}
function selectTab(name) {
  tab = name;
  renderSide();
}
function renderSide() {
  $("#actorTab").setAttribute("aria-pressed", tab === "actors");
  $("#reserveTab").setAttribute("aria-pressed", tab === "reserves");
  $("#healthTab").setAttribute("aria-pressed", tab === "health");
  $("#stageTab").setAttribute("aria-pressed", tab === "stage");
  const el = $("#sideContent"),
    s = project.stage;
  if (tab === "actors") {
    el.innerHTML =
      Object.entries(s.actors)
        .map(
          ([name, a], i) =>
            '<button class="actor-card ' +
            (actorName === name ? "active" : "") +
            '" data-actor="' +
            i +
            '" title="编辑纸片">' +
            thumb(a, name) +
            '<span><b class="actor-name">' +
            esc(name) +
            '</b><span class="marker">' +
            cardKind(a) +
            " · ID " +
            a.marker_id +
            " · " +
            xyLabel(a.start_mm) +
            ' mm</span></span><span class="arrow">' +
            icon("arrow") +
            "</span></button>",
        )
        .join("") +
      '<button class="add-actor" id="addActor">' +
      icon("plus") +
      '添加纸片</button><div class="mini-meta"><span>棋盘尺寸</span><strong>' +
      s.size_mm.join(" × ") +
      " mm</strong></div>";
    el.querySelectorAll("[data-actor]").forEach(
      (b) =>
        (b.onclick = () => {
          actorName = Object.keys(s.actors)[Number(b.dataset.actor)];
          renderSide();
          draw();
          actorDialog(actorName);
        }),
    );
    $("#addActor").onclick = () => actorDialog(null);
  } else if (tab === "reserves") {
    const reserves = s.reserves || [];
    el.innerHTML =
      reserves
        .map((r, i) => {
          const cards = Object.entries(s.actors)
            .filter(([, a]) =>
              a.start_mm.every(
                (v, axis) =>
                  v >= r.origin_mm[axis] &&
                  v <= r.origin_mm[axis] + r.size_mm[axis],
              ),
            )
            .map(([name]) => name);
          return (
            '<button class="reserve-row" data-reserve="' +
            i +
            '"><strong>' +
            esc(r.name) +
            "</strong><span>" +
            esc(xyLabel(r.origin_mm)) +
            " mm · " +
            esc(r.size_mm.join(" × ")) +
            " mm</span><small>" +
            (cards.length ? esc(cards.join("、")) : "暂无预置纸片") +
            "</small></button>"
          );
        })
        .join("") +
      '<button class="add-actor" id="addReserve">' +
      icon("plus") +
      "添加候场区</button>";
    el.querySelectorAll("[data-reserve]").forEach(
      (b) => (b.onclick = () => reserveDialog(Number(b.dataset.reserve))),
    );
    $("#addReserve").onclick = () => reserveDialog(null);
  } else if (tab === "health") {
    const bars = s.health_bars || [];
    el.innerHTML =
      bars
        .map(
          (bar, i) =>
            `<button class="reserve-row hp-row" data-bar="${i}"><strong>${esc(bar.name)}</strong><span>${esc(bar.actor)} · ${bar.tokens.length} 格</span><small>${esc(bar.tokens.join("、"))}</small></button>`,
        )
        .join("") +
      '<button id="addBar" class="add-actor">' +
      icon("plus") +
      "添加血条区</button>";
    el.querySelectorAll("[data-bar]").forEach(
      (b) => (b.onclick = () => healthDialog(Number(b.dataset.bar))),
    );
    $("#addBar").onclick = () => healthDialog(null);
  } else {
    el.innerHTML =
      '<form id="stageForm">' +
      '<div class="field-row">' +
      field("宽度 mm", num("sw", s.size_mm[0], 1)) +
      field("高度 mm", num("sh", s.size_mm[1], 1)) +
      "</div>" +
      '<div class="field-row">' +
      field("格距 mm", num("cell", s.cell_mm, 0.1)) +
      field("放置容差 mm", num("tol", s.placement_tolerance_mm, 0)) +
      "</div>" +
      coordinateFields("相机遮挡时的避让位置 mm", "park", s.park_mm) +
      '<button class="outline" type="submit">应用棋盘设置</button></form>';
    $("#stageForm").onsubmit = async (e) => {
      e.preventDefault();
      try {
        const next = clone(project);
        Object.assign(next.stage, {
          size_mm: [v("sw"), v("sh")],
          cell_mm: v("cell"),
          placement_tolerance_mm: v("tol"),
          park_mm: pair("park"),
        });
        await api("/api/validate", next);
        edit(() => (project = next));
        status("棋盘设置已更新");
      } catch (err) {
        status(err.message);
      }
    };
  }
}
function reserveDialog(index) {
  const reserves = project.stage.reserves || [];
  const current =
    index === null
      ? {
          name: "",
          origin_mm: [0, 0],
          size_mm: project.stage.size_mm.map((v) => Math.min(v, 50)),
        }
      : reserves[index];
  modal(
    index === null ? "新增候场区" : "编辑候场区",
    field(
      "区域名称",
      '<input id="reserveName" required value="' + esc(current.name) + '">',
    ) +
      coordinateFields("左下角位置 mm", "reserveOrigin", current.origin_mm) +
      '<div class="field-row">' +
      field("宽度 mm", num("reserveW", current.size_mm[0], 0.1)) +
      field("高度 mm", num("reserveH", current.size_mm[1], 0.1)) +
      "</div>",
    (index !== null
      ? '<button type="button" class="danger" id="deleteReserve">删除区域</button>'
      : "") + saveBtn("保存区域"),
    async () => {
      const name = $("#reserveName").value.trim();
      if (!name || reserves.some((r, i) => i !== index && r.name === name))
        throw Error("请输入不重复的候场区名称");
      const origin = pair("reserveOrigin"),
        size = [v("reserveW"), v("reserveH")];
      checkStagePoint(origin);
      checkStagePoint(origin.map((v, i) => v + size[i]));
      const next = clone(project);
      next.stage.reserves ??= [];
      next.stage.reserves[index ?? reserves.length] = {
        name,
        origin_mm: origin,
        size_mm: size,
      };
      await api("/api/validate", next);
      edit(() => {
        project = next;
      });
      $("#dialog").close();
    },
  );
  if (index !== null)
    $("#deleteReserve").onclick = () => {
      edit(() => project.stage.reserves.splice(index, 1));
      $("#dialog").close();
    };
}
function healthDialog(index) {
  const stage = project.stage,
    bars = stage.health_bars || [];
  const current = bars[index];
  const others = bars.filter((_, i) => i !== index);
  const available = Object.keys(stage.actors).filter(
    (name) =>
      stage.actors[name].kind !== "prop" &&
      !others.some((bar) => bar.actor === name),
  );
  const props = Object.keys(stage.actors).filter(
    (name) =>
      stage.actors[name].kind === "prop" &&
      !others.some((bar) => bar.tokens.includes(name)),
  );
  if (!available.length) {
    status("请先在“角色与道具”添加一名尚未绑定血条的角色。");
    return;
  }
  const actor = current?.actor || available[0];
  const name = current?.name || actor + "血条";
  modal(
    current ? "编辑血条区" : "添加血条区",
    field("名称", '<input id="hpName" required value="' + esc(name) + '">') +
      field(
        "所属角色",
        '<select id="hpOwner">' +
          available
            .map(
              (n) =>
                "<option " +
                (n === actor ? "selected" : "") +
                ">" +
                esc(n) +
                "</option>",
            )
            .join("") +
          "</select>",
      ) +
      (!current
        ? field(
            "血块来源",
            '<select id="hpSource"><option value="generate">生成并摆放红块</option><option value="select">选择已有道具</option></select>',
          ) +
          '<div id="hpAuto">' +
          field(
            "生成格数",
            '<input id="hpCount" required type="number" min="1" max="50" step="1" value="3">',
          ) +
          "</div>"
        : "") +
      '<div id="hpManual"><fieldset class="hp-tokens"><legend>每张红块代表 1 格血量</legend>' +
      props
        .map(
          (n, i) =>
            `<label><input type="checkbox" data-hp-token="${i}" ${current?.tokens.includes(n) ? "checked" : ""}> ${esc(n)} · ID ${stage.actors[n].marker_id}</label>`,
        )
        .join("") +
      "</fieldset>" +
      '<button type="button" id="fitBar" class="outline">按所选纸片的起点划区</button></div>' +
      coordinateFields(
        "左下角 mm",
        "hpOrigin",
        current?.origin_mm || [0, Math.max(0, stage.size_mm[1] - 30)],
      ) +
      '<div class="field-row">' +
      field(
        "宽 mm",
        num(
          "hpWidth",
          current?.size_mm[0] || Math.min(stage.size_mm[0], 84),
          0.1,
        ),
      ) +
      field(
        "高 mm",
        num(
          "hpHeight",
          current?.size_mm[1] || Math.min(stage.size_mm[1], 30),
          0.1,
        ),
      ) +
      "</div>",
    (current
      ? '<button type="button" id="deleteBar" class="danger">删除血条区</button>'
      : "") + saveBtn("保存血条"),
    async () => {
      const next = clone(project);
      const tokens = selected();
      const generate = $("#hpSource")?.value === "generate";
      const name = $("#hpName").value.trim();
      if (!name || others.some((b) => b.name === name))
        throw Error("请填写不同的血条名称");
      if (!generate && !tokens.length)
        throw Error("请勾选至少一张道具作为血块");
      const bar = {
        name,
        actor: $("#hpOwner").value,
        tokens,
        origin_mm: pair("hpOrigin"),
        size_mm: [v("hpWidth"), v("hpHeight")],
      };
      checkStagePoint(bar.origin_mm);
      checkStagePoint(bar.origin_mm.map((n, i) => n + bar.size_mm[i]));
      if (generate) {
        tokens.length = 0;
        const count = v("hpCount");
        const { side, positions } = layoutTokens(
          bar.origin_mm,
          bar.size_mm,
          count,
        );
        const actors = next.stage.actors;
        const used = new Set(Object.values(actors).map((a) => a.marker_id));
        const ids = Array.from({ length: 50 }, (_, i) => i).filter(
          (n) => !used.has(n),
        );
        if (ids.length < count)
          throw Error("仅剩 " + ids.length + " 个可用定位编号，请减少格数");
        const canvas = document.createElement("canvas");
        canvas.width = canvas.height = 96;
        const paint = canvas.getContext("2d");
        paint.fillStyle = "#c9433d";
        paint.fillRect(0, 0, 96, 96);
        const image = canvas.toDataURL("image/png");
        let suffix = 1;
        for (const [i, point] of positions.entries()) {
          for (const [other, card] of Object.entries(actors)) {
            const center = card.start_mm.map(
              (v, axis) =>
                v -
                card.pickup_offset_mm[axis] -
                (card.marker_offset_mm?.[axis] || 0),
            );
            if (
              point.every(
                (n, axis) =>
                  Math.abs(n - center[axis]) <
                  (side + card.print_size_mm[axis]) / 2,
              )
            )
              throw Error(
                "新红块与「" +
                  other +
                  "」的初始纸片重叠，请移动血条区或调整摆位。",
              );
          }
          let token;
          do {
            token = bar.actor + "血块" + suffix++;
          } while (Object.hasOwn(actors, token));
          actors[token] = {
            kind: "prop",
            marker_id: ids[i],
            start_mm: point,
            print_size_mm: [side, side],
            pickup_offset_mm: [0, 0],
            marker_offset_mm: [0, 0],
            image,
          };
          tokens.push(token);
        }
      }
      if (tokens.some((n) => !inHealthBar(bar, next.stage.actors[n].start_mm)))
        throw Error("血块起点应在本区内。可点击“按所选纸片的起点划区”。");
      next.stage.health_bars ??= [];
      next.stage.health_bars[index ?? bars.length] = bar;
      await api("/api/validate", next);
      edit(() => (project = next));
      $("#dialog").close();
    },
  );
  if ($("#hpSource")) {
    const updateSource = () => {
      const generate = $("#hpSource").value === "generate";
      $("#hpAuto").hidden = !generate;
      $("#hpCount").disabled = !generate;
      $("#hpManual").hidden = generate;
    };
    $("#hpSource").onchange = updateSource;
    updateSource();
  }
  $("#hpOwner").onchange = () => {
    const input = $("#hpName");
    if (!current && available.some((n) => input.value === n + "血条"))
      input.value = $("#hpOwner").value + "血条";
  };
  const selected = () =>
    [...document.querySelectorAll("[data-hp-token]:checked")].map(
      (el) => props[+el.dataset.hpToken],
    );
  $("#fitBar").onclick = () => {
    const cards = selected().map((n) => stage.actors[n]);
    if (!cards.length) {
      $("#dialogError").textContent = "请先勾选血块。";
      return;
    }
    const origins = [],
      sizes = [];
    for (let axis = 0; axis < 2; axis++) {
      const centers = cards.map(
        (c) =>
          c.start_mm[axis] -
          c.pickup_offset_mm[axis] -
          (c.marker_offset_mm?.[axis] || 0),
      );
      const lo = Math.max(
        0,
        Math.min(
          ...cards.map((c, i) => centers[i] - c.print_size_mm[axis] / 2),
        ) - 2,
      );
      const hi = Math.min(
        stage.size_mm[axis],
        Math.max(
          ...cards.map((c, i) => centers[i] + c.print_size_mm[axis] / 2),
        ) + 2,
      );
      origins.push(lo);
      sizes.push(hi - lo);
    }
    ["hpOriginX", "hpOriginY", "hpWidth", "hpHeight"].forEach(
      (id, i) => ($("#" + id).value = nfmt([...origins, ...sizes][i])),
    );
    $("#dialogError").textContent = "";
  };
  if (current)
    $("#deleteBar").onclick = () => {
      edit(() => bars.splice(index, 1));
      $("#dialog").close();
    };
}
function renderSequence() {
  const steps = project.show.steps;
  $("#stepCount").textContent = steps.length + " 步";
  $("#sequence").innerHTML = steps.length
    ? steps
        .map(
          (s, i) =>
            '<button class="step-line ' +
            (i === stepIndex ? "active" : "") +
            '" aria-pressed="' +
            (i === stepIndex) +
            '" data-step="' +
            i +
            '"><span class="index">' +
            String(i + 1).padStart(2, "0") +
            '</span><span class="op-tag op-' +
            s.op +
            '">' +
            actionName(s) +
            '</span><span class="step-desc">' +
            esc(
              s.op === "move"
                ? s.actor + " → (" + xyLabel(s.to_mm) + ")"
                : s.op === "cue"
                  ? s.text
                  : s.seconds + " 秒",
            ) +
            "</span></button>",
        )
        .join("")
    : '<p class="empty">添加第一个动作开始编排。</p>';
  $("#sequence")
    .querySelectorAll("[data-step]")
    .forEach(
      (b) =>
        (b.onclick = () => {
          pick = null;
          stepIndex = +b.dataset.step;
          if (project.show.steps[stepIndex].op === "move")
            actorName = project.show.steps[stepIndex].actor;
          render();
        }),
    );
}
function moveStep(d) {
  const i = stepIndex,
    j = i + d;
  if (j < 0 || j >= project.show.steps.length) return;
  edit(() => {
    const steps = project.show.steps;
    [steps[j], steps[i]] = [steps[i], steps[j]];
    stepIndex = j;
  });
  scrollStep();
}
function scrollStep() {
  const b = $("#sequence .active"),
    container = $("#sequence");
  if (b)
    container.scrollTop +=
      b.getBoundingClientRect().top -
      container.getBoundingClientRect().top -
      10;
}
function delStep() {
  edit(() => project.show.steps.splice(stepIndex, 1));
}
function renderStep() {
  const s = project.show.steps[stepIndex],
    el = $("#stepInspector");
  if (!s) {
    el.innerHTML = "";
    return;
  }
  const tool = (id, k, label, off = false) =>
    '<button id="' +
    id +
    '" title="' +
    label +
    '" aria-label="' +
    label +
    '" ' +
    (off ? "disabled" : "") +
    ">" +
    icon(k) +
    "</button>";
  el.innerHTML =
    '<div class="step-title"><h3>第 ' +
    (stepIndex + 1) +
    " 步 · " +
    actionName(s) +
    '</h3><div class="edit-buttons">' +
    tool("up", "up", "向前移", stepIndex === 0) +
    tool(
      "down",
      "down",
      "向后移",
      stepIndex === project.show.steps.length - 1,
    ) +
    tool("del", "trash", "删除动作") +
    "</div></div>";
  if (s.op === "cue")
    el.insertAdjacentHTML(
      "beforeend",
      field("字幕", '<textarea id="cueText">' + esc(s.text) + "</textarea>"),
    );
  else if (s.op === "wait")
    el.insertAdjacentHTML(
      "beforeend",
      field("等待时长（秒）", num("waitSeconds", s.seconds, 0)),
    );
  else {
    const names = Object.keys(project.stage.actors);
    el.insertAdjacentHTML(
      "beforeend",
      field(
        "操作纸片",
        '<select id="moveActor">' +
          names
            .map(
              (n) =>
                "<option " +
                (s.actor === n ? "selected" : "") +
                ">" +
                esc(n) +
                "</option>",
            )
            .join("") +
          "</select>",
      ) +
        field(
          "操作方式",
          '<select id="moveMethod"><option value="carry">吸取搬运</option><option value="push" ' +
            (isPush(s) ? "selected" : "") +
            ">直线平推</option></select>",
        ) +
        coordinateFields("目标位置 mm", "to", s.to_mm, true) +
        (isPush(s)
          ? pushDistanceField("pushBack", s.push_back_mm)
          : '<div class="field-pair"><span class="subheading">途经点（按顺序）</span><button id="addVia" class="waypoint-add">' +
            icon("plus") +
            "添加途经点</button></div>" +
            (s.via_mm || [])
              .map(
                (p, i) =>
                  '<div class="waypoint"><span class="index">' +
                  (i + 1) +
                  "</span>" +
                  coordinateFields("途经点 " + (i + 1), "via" + i, p, true) +
                  '<button data-remove="' +
                  i +
                  '" aria-label="删除途经点 ' +
                  (i + 1) +
                  '">' +
                  icon("close") +
                  "</button></div>",
              )
              .join("")),
    );
  }
  $("#up").onclick = () => moveStep(-1);
  $("#down").onclick = () => moveStep(1);
  $("#del").onclick = delStep;
  function change(id, fn) {
    $("#" + id).onchange = () => {
      try {
        fn();
      } catch (err) {
        status(err.message);
        renderStep();
      }
    };
  }
  if (s.op === "cue")
    change("cueText", () => {
      const text = $("#cueText").value.trim();
      if (!text) throw Error("请填写字幕");
      edit(() => (s.text = text));
    });
  else if (s.op === "wait")
    change("waitSeconds", () => {
      const seconds = v("waitSeconds");
      edit(() => (s.seconds = seconds));
    });
  else {
    change("moveActor", () => {
      const n = $("#moveActor").value;
      edit(() => {
        s.actor = n;
        actorName = n;
      });
    });
    change("moveMethod", () => {
      const method = $("#moveMethod").value;
      if (
        method === "push" &&
        s.via_mm?.length &&
        !confirm("平推只沿直线，切换后将移除本步途经点。继续？")
      ) {
        renderStep();
        return;
      }
      edit(() => {
        s.method = method;
        if (method === "push") {
          delete s.via_mm;
          s.push_back_mm = defaultPushBack(s.actor);
        } else {
          delete s.push_back_mm;
          s.via_mm = [];
        }
      });
    });
    if (isPush(s))
      change("pushBack", () => {
        const mm = v("pushBack");
        edit(() => (s.push_back_mm = mm));
      });
    const keys = ["to", ...(s.via_mm || []).map((_, i) => "via" + i)];
    for (const k of keys)
      for (const axis of ["X", "Y"])
        change(k + axis, () => {
          const p = pair(k);
          checkStagePoint(p);
          edit(() => setRoutePoint(k, p));
        });
    if (!isPush(s))
      $("#addVia").onclick = () => {
        if (!s.via_mm) s.via_mm = [];
        const p = s.via_mm.at(-1) || startOfMove();
        edit(() => s.via_mm.push(p.map((n, i) => nfmt((n + s.to_mm[i]) / 2))));
      };
    el.querySelectorAll("[data-remove]").forEach(
      (b) =>
        (b.onclick = () => edit(() => s.via_mm.splice(+b.dataset.remove, 1))),
    );
    el.querySelectorAll("[data-pick]").forEach(
      (b) =>
        (b.onclick = () => {
          editMode();
          pick = pick === b.dataset.pick ? null : b.dataset.pick;
          draw();
          if (pick)
            board.scrollIntoView({ block: "nearest", behavior: "smooth" });
        }),
    );
  }
}
function startOfMove() {
  const steps = project.show.steps,
    s = steps[stepIndex];
  for (let i = stepIndex - 1; i >= 0; i--)
    if (steps[i].op === "move" && steps[i].actor === s.actor)
      return steps[i].to_mm;
  return project.stage.actors[s.actor].start_mm;
}
function setRoutePoint(key, p) {
  const s = project.show.steps[stepIndex];
  if (key === "to") s.to_mm = p;
  else s.via_mm[+key.slice(3)] = p;
}

function modal(title, html, actions, submit) {
  pause();
  for (const sel of ["#dialogTitle", "#dialogBody", "#dialogFoot"])
    $(sel).replaceChildren();
  $("#dialogTitle").textContent = title;
  $("#dialogBody").innerHTML =
    html + '<p id="dialogError" class="dialog-error" role="alert"></p>';
  $("#dialogFoot").innerHTML = actions;
  $("#dialogForm").onsubmit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    submitting = true;
    try {
      await submit();
    } catch (err) {
      $("#dialogError").textContent = err.message;
    } finally {
      submitting = false;
    }
  };
  $("#dialog").showModal();
}
const saveBtn = (label) =>
  '<button type="submit" class="primary">' + label + "</button>";
$("#closeDialog").onclick = () => $("#dialog").close();
function titleDialog() {
  modal(
    "编辑剧名",
    field(
      "剧目名称",
      '<input id="showTitle" required value="' + esc(project.show.title) + '">',
    ),
    saveBtn("保存"),
    () => {
      const val = $("#showTitle").value.trim();
      if (!val) throw Error("请填写剧名");
      edit(() => (project.show.title = val));
      $("#dialog").close();
    },
  );
}
function actorDialog(old) {
  const names = Object.keys(project.stage.actors),
    existing = project.stage.actors[old],
    used = new Set(Object.values(project.stage.actors).map((a) => a.marker_id));
  const free = Array.from({ length: 50 }, (_, i) => i).find(
    (i) => !used.has(i),
  );
  if (!existing && free === undefined) {
    status("50 个纸片标记已用完");
    return;
  }
  const a = clone(
    existing || {
      image: null,
      marker_id: free,
      print_size_mm: [40, 40],
      pickup_offset_mm: [0, 0],
      start_mm: project.stage.size_mm.map((n) => nfmt(n / 2)),
    },
  );
  let fileBusy = false;
  modal(
    existing ? "编辑纸片" : "添加纸片",
    '<div class="actor-summary"><div id="imageThumb">' +
      thumb(a, old || "角") +
      '</div><button type="button" id="uploadPick" class="secondary">' +
      icon("image") +
      '上传插图</button><input id="actorFile" type="file" accept="image/*" hidden></div>' +
      field(
        "纸片名称",
        '<input id="actorName" required value="' + esc(old || "") + '">',
      ) +
      field(
        "纸片类型",
        '<select id="cardKind"><option value="actor">角色</option><option value="prop" ' +
          (a.kind === "prop" ? "selected" : "") +
          ">道具 / 特效</option></select>",
      ) +
      '<div class="field-row">' +
      field(
        "标记 ID（0–49）",
        '<input type="number" id="markerId" min="0" max="49" step="1" required value="' +
          a.marker_id +
          '">',
      ) +
      field("纸卡宽 mm", num("printW", a.print_size_mm[0], 16)) +
      field("纸卡高 mm", num("printH", a.print_size_mm[1], 16)) +
      "</div>" +
      ((project.stage.reserves || []).length
        ? field(
            "预置位置",
            '<select id="placeAt"><option value="">自定坐标</option>' +
              project.stage.reserves
                .map(
                  (r, i) =>
                    '<option value="' +
                    i +
                    '">' +
                    esc(r.name) +
                    " · 中心</option>",
                )
                .join("") +
              "</select>",
          )
        : "") +
      coordinateFields("初始吸取点 mm", "start", a.start_mm) +
      coordinateFields(
        "图中心 → 标记中心偏移 mm",
        "markerOffset",
        a.marker_offset_mm || [0, 0],
      ) +
      coordinateFields(
        "标记中心 → 吸取点偏移 mm",
        "offset",
        a.pickup_offset_mm,
      ),
    (existing
      ? '<button type="button" class="danger" id="deleteActor">删除纸片</button>'
      : "") + saveBtn(existing ? "保存纸片" : "添加到舞台"),
    async () => {
      if (fileBusy) throw Error("正在读取图片，请稍候");
      const name = $("#actorName").value.trim();
      if (!name) throw Error("请填写纸片名称");
      if (name !== old && Object.hasOwn(project.stage.actors, name))
        throw Error("纸片名称已存在");
      if (!existing && names.length >= 50) throw Error("纸片标记数已达上限");
      a.kind = $("#cardKind").value;
      a.marker_id = v("markerId");
      if (
        names.some(
          (n) => n !== old && project.stage.actors[n].marker_id === a.marker_id,
        )
      )
        throw Error("标记 ID 已被使用");
      a.print_size_mm = [v("printW"), v("printH")];
      a.marker_offset_mm = pair("markerOffset");
      a.pickup_offset_mm = pair("offset");
      a.start_mm = pair("start");
      checkStagePoint(a.start_mm);
      if (
        a.pickup_offset_mm.some(
          (n, i) =>
            Math.abs(n + a.marker_offset_mm[i]) > a.print_size_mm[i] / 2,
        )
      )
        throw Error("吸取点应位于纸卡内");
      const next = clone(project);
      next.stage.actors = Object.fromEntries(
        names
          .map((n) => (n === old ? [name, a] : [n, next.stage.actors[n]]))
          .concat(existing ? [] : [[name, a]]),
      );
      if (
        old &&
        next.stage.health_bars?.some(
          (b) =>
            (b.actor === old && a.kind === "prop") ||
            (b.tokens.includes(old) && a.kind !== "prop"),
        )
      )
        throw Error("请先在血条面板解除这张纸片的绑定，再修改其类型。");
      if (old && next.stage.health_bars && old !== name)
        next.stage.health_bars = updateHealthReferences(
          next.stage.health_bars,
          old,
          name,
        );
      if (old && name !== old)
        for (const s of next.show.steps)
          if (s.op === "move" && s.actor === old) s.actor = name;
      await api("/api/validate", next);
      edit(() => {
        project = next;
        actorName = name;
      });
      $("#dialog").close();
    },
  );
  if ($("#placeAt"))
    $("#placeAt").onchange = (e) => {
      if (e.target.value === "") return;
      const r = project.stage.reserves[Number(e.target.value)];
      $("#startX").value = nfmt(r.origin_mm[0] + r.size_mm[0] / 2);
      $("#startY").value = nfmt(r.origin_mm[1] + r.size_mm[1] / 2);
    };
  $("#uploadPick").onclick = () => $("#actorFile").click();
  $("#actorFile").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    fileBusy = true;
    $("#uploadPick").disabled = true;
    const url = URL.createObjectURL(f);
    try {
      const img = new Image();
      img.src = url;
      await img.decode();
      const factor = Math.min(1, 1200 / Math.max(img.width, img.height)),
        c = document.createElement("canvas");
      c.width = Math.max(1, Math.round(img.width * factor));
      c.height = Math.max(1, Math.round(img.height * factor));
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      a.image = c.toDataURL("image/png");
      $("#imageThumb").innerHTML = thumb(a, old || f.name);
      if (!existing) {
        if (!$("#actorName").value)
          $("#actorName").value = f.name.replace(/\.[^.]+$/, "");
        const r = c.width / c.height;
        $("#printW").value = nfmt(Math.max(16, 40 * Math.min(1, r)));
        $("#printH").value = nfmt(Math.max(16, 40 * Math.min(1, 1 / r)));
      }
      $("#dialogError").textContent = "";
    } catch {
      $("#dialogError").textContent =
        "无法读取图片，请选择 PNG、JPEG 或 WebP 等浏览器能打开的图像。";
    } finally {
      fileBusy = false;
      $("#uploadPick").disabled = false;
      URL.revokeObjectURL(url);
    }
  };
  if (existing)
    $("#deleteActor").onclick = () => {
      if (names.length === 1) {
        $("#dialogError").textContent = "舞台至少需要一张纸片";
        return;
      }
      const linked = project.show.steps.filter(
        (s) => s.op === "move" && s.actor === old,
      ).length;
      if (
        !confirm(
          "删除「" +
            old +
            "」" +
            (linked ? "及其 " + linked + " 个移动动作" : "") +
            ((project.stage.health_bars || []).some(
              (b) => b.actor === old || b.tokens.includes(old),
            )
              ? "，并更新关联血条"
              : "") +
            "？",
        )
      )
        return;
      edit(() => {
        delete project.stage.actors[old];
        if (project.stage.health_bars)
          project.stage.health_bars = updateHealthReferences(
            project.stage.health_bars,
            old,
            null,
          );
        project.show.steps = project.show.steps.filter(
          (s) => s.op !== "move" || s.actor !== old,
        );
      });
      $("#dialog").close();
    };
}
function defaultPushBack(name) {
  return nfmt(Math.min(...project.stage.actors[name].print_size_mm) / 2);
}
function pushDistanceField(id, mm) {
  return (
    field("定位吸点到后缘推耳的实测距离 mm", num(id, mm, 0.01)) +
    '<p class="dialog-text">沿直线贴着棋盘推行，推头抵住纸卡后缘或折起的推耳。按实际推进方向量取上面的距离。</p>'
  );
}
function addStepDialog() {
  modal(
    "添加动作",
    field(
      "动作类型",
      '<select id="stepType"><option value="move">吸取搬运</option><option value="push">直线平推</option><option value="cue">显示字幕</option><option value="wait">等待</option></select>',
    ) + '<div id="newStepFields"></div>',
    saveBtn("插入动作"),
    () => {
      const op = $("#stepType").value;
      let step;
      if (op === "move" || op === "push") {
        const actor = $("#addWho").value,
          to = pair("addTo");
        checkStagePoint(to);
        step =
          op === "push"
            ? {
                op: "move",
                method: "push",
                actor,
                to_mm: to,
                push_back_mm: v("newPushBack"),
              }
            : { op: "move", actor, to_mm: to, via_mm: [] };
      } else if (op === "cue") {
        const text = $("#addCue").value.trim();
        if (!text) throw Error("请填写字幕");
        step = { op, text };
      } else step = { op, seconds: v("addWait") };
      edit(() => {
        stepIndex++;
        project.show.steps.splice(stepIndex, 0, step);
      });
      $("#dialog").close();
      scrollStep();
    },
  );
  const fields = () => {
    const op = $("#stepType").value;
    $("#newStepFields").innerHTML =
      op === "move" || op === "push"
        ? field(
            "操作纸片",
            '<select id="addWho">' +
              Object.keys(project.stage.actors)
                .map(
                  (n) =>
                    "<option " +
                    (actorName === n ? "selected" : "") +
                    ">" +
                    esc(n) +
                    "</option>",
                )
                .join("") +
              "</select>",
          ) +
          coordinateFields(
            "目标位置 mm",
            "addTo",
            project.stage.size_mm.map((n) => nfmt(n / 2)),
          ) +
          (op === "push"
            ? pushDistanceField("newPushBack", defaultPushBack(actorName))
            : "")
        : op === "cue"
          ? field("字幕", '<textarea required id="addCue"></textarea>')
          : field("等待时长（秒）", num("addWait", 1, 0));
  };
  $("#stepType").onchange = fields;
  fields();
}
function printDialog() {
  modal(
    "打印舞台素材",
    field(
      "纸张",
      '<select id="paper"><option>A4</option><option>A3</option><option>A5</option><option>A2</option></select>',
    ) +
      field(
        "纸张方向",
        '<select id="orient"><option value="landscape">横向</option><option value="portrait">纵向</option></select>',
      ) +
      field(
        "打印内容",
        '<select id="parts"><option value="all">棋盘与全部纸片</option><option value="board">棋盘背景</option><option value="actors">角色和道具纸卡</option><option value="calibration">自动标定码（棋盘四角与吸盘）</option></select>',
      ) +
      '<p class="dialog-text">按 100% 实际尺寸打印。超过一页的棋盘会分成多页供拼接。</p>',
    saveBtn("生成打印图"),
    () => {
      printStage(project, {
        paper: $("#paper").value,
        orientation: $("#orient").value,
        content: $("#parts").value,
      });
      $("#dialog").close();
    },
  );
}
function makeNew() {
  modal(
    "新建剧目",
    field("剧名", '<input id="newTitle" required placeholder="未命名剧目">'),
    saveBtn("创建"),
    () => {
      const title = $("#newTitle").value.trim();
      if (!title) throw Error("请填写剧名");
      edit(() => {
        project = {
          version: 1,
          stage: {
            size_mm: [300, 200],
            cell_mm: 25,
            park_mm: [10, 190],
            placement_tolerance_mm: 3,
            reserves: [],
            actors: {
              角色一: {
                start_mm: [50, 75],
                marker_id: 1,
                pickup_offset_mm: [0, 0],
                print_size_mm: [40, 40],
                image: null,
              },
            },
          },
          show: { title, steps: [] },
        };
        stepIndex = -1;
      });
      $("#dialog").close();
    },
  );
}
async function importProject(f) {
  const p = JSON.parse(await f.text());
  await api("/api/validate", p);
  edit(() => {
    project = p;
    actorName = Object.keys(p.stage.actors)[0];
    stepIndex = p.show.steps.length ? 0 : -1;
  });
  status("已导入 " + p.show.title);
}
function download() {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(project, null, 2) + "\n"], {
      type: "application/json",
    }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download =
    project.show.title.replace(/[\\/:*?"<>|]/g, "_") + ".armischestra.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

function updateControls() {
  $("#modeEdit").setAttribute("aria-pressed", !previewMode);
  $("#modePreview").setAttribute("aria-pressed", previewMode);
  $("#play").innerHTML =
    icon(playing ? "pause" : "play") +
    "<span>" +
    (playing ? "暂停" : "播放预演") +
    "</span>";
  $("#timer").textContent =
    t.toFixed(1) +
    (preview ? " / " + preview.duration_s.toFixed(1) : "") +
    " s";
  $("#scrub").value =
    preview && preview.duration_s
      ? Math.round((t / preview.duration_s) * 10000)
      : 0;
}
async function ensurePreview() {
  if (!preview) {
    const rev = revision;
    const result = await api("/api/rehearse", project);
    if (rev !== revision) return false;
    preview = result;
  }
  return true;
}
let intent = 0;
async function beginPreview(playNow) {
  const request = ++intent;
  try {
    if (!(await ensurePreview()) || request !== intent) return;
    previewMode = true;
    pick = null;
    if (playNow && preview.duration_s > 0) {
      if (t >= preview.duration_s) t = 0;
      playing = true;
      last = performance.now();
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(tick);
    }
    updateControls();
    draw();
  } catch (err) {
    status(err.message);
  }
}
function tick(now) {
  if (!playing || !preview) return;
  const dt = (now - last) / 1000;
  last = now;
  t = Math.min(preview.duration_s, t + dt * Number($("#speed").value));
  if (t >= preview.duration_s) pause();
  else raf = requestAnimationFrame(tick);
  updateControls();
  draw();
}
function frameAt() {
  const ev = preview.events;
  let lo = 0,
    hi = ev.length;
  while (lo + 1 < hi) {
    const mid = (lo + hi) >> 1;
    if (ev[mid].time_s <= t) lo = mid;
    else hi = mid;
  }
  const a = ev[lo],
    b = ev[lo + 1];
  if (!b || b.action !== "move_xy" || b.time_s <= a.time_s) return a;
  const q = Math.max(0, Math.min(1, (t - a.time_s) / (b.time_s - a.time_s)));
  const mix = (p, n) => [p[0] + (n[0] - p[0]) * q, p[1] + (n[1] - p[1]) * q];
  return {
    ...a,
    arm: mix(a.arm, b.arm),
    actors: Object.fromEntries(
      Object.entries(a.actors).map(([k, p]) => [k, mix(p, b.actors[k])]),
    ),
  };
}

function imageFor(source) {
  if (!source) return null;
  if (!images.has(source)) {
    const image = new Image();
    image.onload = draw;
    image.src = source;
    images.set(source, image);
  }
  const img = images.get(source);
  return img.complete && img.naturalWidth ? img : null;
}
function geometryOf(w, h) {
  const [sw, sh] = project.stage.size_mm,
    scale = Math.min((w - 92) / sw, (h - 54) / sh),
    gw = sw * scale,
    gh = sh * scale,
    left = (w - gw) / 2,
    top = (h - gh) / 2 - 2;
  return {
    scale,
    left,
    top,
    gw,
    gh,
    point: ([x, y]) => [left + x * scale, top + gh - y * scale],
  };
}
function draw() {
  if (!project) return;
  const { width: w, height: h } = board.getBoundingClientRect(),
    dpr = window.devicePixelRatio || 1;
  if (w <= 0 || h <= 0) return;
  if (
    board.width !== Math.round(w * dpr) ||
    board.height !== Math.round(h * dpr)
  ) {
    board.width = Math.round(w * dpr);
    board.height = Math.round(h * dpr);
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  const s = project.stage,
    g = (geometry = geometryOf(w, h)),
    [sw, sh] = s.size_mm;
  const { scale, left, top, gw, gh } = g;
  const frame = previewMode && preview ? frameAt() : null;
  ctx.save();
  ctx.shadowBlur = 11;
  ctx.shadowColor = "#20312132";
  ctx.shadowOffsetY = 4;
  ctx.fillStyle = "#fffcf0";
  ctx.fillRect(left - 4, top - 4, gw + 8, gh + 8);
  ctx.restore();
  ctx.fillStyle = "#f5f3e7";
  ctx.fillRect(left, top, gw, gh);
  ctx.save();
  ctx.beginPath();
  ctx.rect(left, top, gw, gh);
  ctx.clip();
  // Scale dense boards to a visible ruler interval while preserving actual dimensions.
  const step = s.cell_mm * Math.max(1, Math.ceil(5 / (s.cell_mm * scale)));
  for (let row = 0; row * step < sh; row++)
    for (let col = row % 2; col * step < sw; col += 2) {
      const [x, y] = g.point([col * step, (row + 1) * step]);
      ctx.fillStyle = "#d8dfcb";
      ctx.fillRect(x, y, step * scale + 0.15, step * scale + 0.15);
    }
  ctx.strokeStyle = "#8f9b853c";
  ctx.lineWidth = 0.65;
  ctx.beginPath();
  for (let x = 0; x <= sw; x += step) {
    let p = g.point([x, 0]);
    ctx.moveTo(p[0], top);
    ctx.lineTo(p[0], top + gh);
  }
  for (let y = 0; y <= sh; y += step) {
    let p = g.point([0, y]);
    ctx.moveTo(left, p[1]);
    ctx.lineTo(left + gw, p[1]);
  }
  ctx.stroke();
  ctx.restore();
  ctx.font = '10px "IBM Plex Mono", monospace';
  ctx.fillStyle = "#536852";
  ctx.textAlign = "center";
  const spacing = step * Math.max(1, Math.ceil(38 / (step * scale)));
  for (let x = 0; x <= sw; x += spacing) {
    const p = g.point([x, 0]);
    ctx.fillText(String(nfmt(x)), p[0], top + gh + 17);
  }
  ctx.textAlign = "right";
  for (let y = 0; y <= sh; y += spacing) {
    const p = g.point([0, y]);
    ctx.fillText(String(nfmt(y)), left - 9, p[1] + 3);
  }
  ctx.textAlign = "left";
  ctx.fillText("Y", left - 18, top - 8);
  ctx.textAlign = "right";
  ctx.fillText("X", left + gw + 15, top + gh + 16);
  const bars = s.health_bars || [];
  const healthTokens = new Set(bars.flatMap((b) => b.tokens));
  const readout = $("#healthReadout");
  const state = bars.map((b) => [
    b.actor,
    healthAt(b, (n) => (frame ? frame.actors[n] : s.actors[n]?.start_mm)),
    b.tokens.length,
  ]);
  const signature = JSON.stringify(state);
  if (readout.dataset.state !== signature) {
    readout.hidden = !state.length;
    readout.innerHTML = state
      .map(
        ([owner, hp, max]) =>
          `<span class="hp-meter"><b>${esc(owner)}</b><span aria-hidden="true">${Array.from({ length: max }, (_, i) => '<i class="' + (i < hp ? "full" : "") + '"></i>').join("")}</span><strong>${hp}/${max}${hp === 0 ? " · 归零" : ""}</strong></span>`,
      )
      .join("");
    readout.dataset.state = signature;
  }
  for (const reserve of [...(s.reserves || []), ...bars]) {
    const [rx, ry] = reserve.origin_mm,
      [rw, rh] = reserve.size_mm;
    const [x, y] = g.point([rx, ry + rh]);
    ctx.save();
    ctx.beginPath();
    ctx.rect(x, y, rw * scale, rh * scale);
    ctx.clip();
    const isHealth = Array.isArray(reserve.tokens);
    ctx.strokeStyle = isHealth ? "#a63734" : "#a25c24";
    ctx.lineWidth = 2.5;
    ctx.setLineDash(isHealth ? [] : [5, 3]);
    ctx.strokeRect(x, y, rw * scale, rh * scale);
    ctx.setLineDash([]);
    ctx.fillStyle = isHealth ? "#953530" : "#724125";
    ctx.font = "600 11px sans-serif";
    ctx.textAlign = "left";
    const name = reserve.name,
      labelWidth = ctx.measureText(name).width + 8;
    ctx.fillRect(x + 1, y + 1, labelWidth, 16);
    ctx.fillStyle = "#fff6df";
    ctx.fillText(name, x + 5, y + 13);
    ctx.restore();
  }
  const park = g.point(s.park_mm);
  ctx.strokeStyle = "#677e69";
  ctx.lineWidth = 1.2;
  ctx.strokeRect(park[0] - 5, park[1] - 5, 10, 10);
  ctx.textAlign = "left";
  ctx.fillStyle = "#526751";
  ctx.font = "10px sans-serif";
  ctx.fillText("避让", park[0] + 8, park[1] + 3);
  const command = project.show.steps[stepIndex];
  if (!frame && command?.op === "move") {
    const start = startOfMove();
    const pts = [start, ...(command.via_mm || []), command.to_mm].map(g.point);
    ctx.save();
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#bd713c";
    if (isPush(command)) {
      const length = Math.hypot(
        command.to_mm[0] - start[0],
        command.to_mm[1] - start[1],
      );
      if (length) {
        const back = start.map(
          (v, i) =>
            v - (command.push_back_mm * (command.to_mm[i] - v)) / length,
        );
        const [bx, by] = g.point(back);
        ctx.fillStyle = "#80395c";
        ctx.fillRect(bx - 3, by - 3, 6, 6);
        ctx.textAlign = "left";
        ctx.font = "10px sans-serif";
        ctx.fillText("推点", bx + 5, by - 4);
      }
    }
    ctx.setLineDash([5, 5]);
    ctx.beginPath();
    pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
    ctx.stroke();
    ctx.setLineDash([]);
    pts.slice(1).forEach(([x, y], i) => {
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = "#fbefd8";
      ctx.fill();
      ctx.stroke();
      if (i === pts.length - 2) {
        ctx.beginPath();
        ctx.arc(x, y, 7, 0, Math.PI * 2);
        ctx.stroke();
      }
    });
    ctx.restore();
  }
  for (const [name, a] of Object.entries(s.actors)) {
    const coord = frame ? frame.actors[name] : a.start_mm;
    const [x, y] = g.point([
      coord[0] - a.pickup_offset_mm[0] - (a.marker_offset_mm?.[0] || 0),
      coord[1] - a.pickup_offset_mm[1] - (a.marker_offset_mm?.[1] || 0),
    ]);
    const pw = a.print_size_mm[0] * scale,
      ph = a.print_size_mm[1] * scale,
      im = imageFor(a.image);
    ctx.save();
    ctx.shadowColor = "#29352e40";
    ctx.shadowBlur = 3;
    ctx.shadowOffsetY = 2;
    if (im) {
      const sz = Math.min(pw / im.width, ph / im.height);
      ctx.drawImage(
        im,
        x - (im.width * sz) / 2,
        y - (im.height * sz) / 2,
        im.width * sz,
        im.height * sz,
      );
    } else {
      ctx.fillStyle =
        Object.keys(s.actors).indexOf(name) % 2 ? "#584d60" : "#c77748";
      ctx.beginPath();
      ctx.arc(x, y, Math.max(3, Math.min(pw, ph) / 2), 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#fff";
      ctx.textAlign = "center";
      ctx.font = "bold " + Math.max(9, Math.min(24, pw / 2)) + "px sans-serif";
      ctx.fillText([...name][0], x, y + 5);
    }
    ctx.restore();
    if ($("#showMarkers").checked) {
      const [mw, mh] = a.print_size_mm,
        [mx, my] = a.marker_offset_mm || [0, 0];
      const art = marker(
        a.marker_id,
        mw / 2 + mx,
        mh / 2 - my,
        Math.min(mw, mh),
        healthTokens.has(name),
      );
      const source =
        "data:image/svg+xml;charset=utf-8," +
        encodeURIComponent(
          '<svg xmlns="http://www.w3.org/2000/svg" width="' +
            mw * 6 +
            '" height="' +
            mh * 6 +
            '" viewBox="0 0 ' +
            mw +
            " " +
            mh +
            '">' +
            art +
            "</svg>",
        );
      const stamp = imageFor(source);
      if (stamp) ctx.drawImage(stamp, x - pw / 2, y - ph / 2, pw, ph);
    }
    const [ax, ay] = g.point(coord);
    if (!frame && name === actorName) {
      const u = 5;
      ctx.strokeStyle = "#597653";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      for (const [dx, dy] of [
        [-1, -1],
        [-1, 1],
        [1, -1],
        [1, 1],
      ]) {
        const xx = x + dx * (pw / 2 + 2),
          yy = y + dy * (ph / 2 + 2);
        ctx.moveTo(xx - dx * u, yy);
        ctx.lineTo(xx, yy);
        ctx.lineTo(xx, yy - dy * u);
      }
      ctx.stroke();
    }
    // The scoreboard identifies blood tokens. Repeated labels obscure neighboring pieces.
    if (!healthTokens.has(name) || (!frame && name === actorName)) {
      const tag = name.length > 16 ? name.slice(0, 15) + "…" : name;
      ctx.font = '600 11px "Noto Sans CJK SC", sans-serif';
      const tw = ctx.measureText(tag).width + 12,
        tx = Math.min(w - tw - 2, Math.max(2, x - tw / 2)),
        ty = Math.min(h - 18, y + ph / 2 + 4);
      ctx.fillStyle = a.kind === "prop" ? "#724125" : "#304636";
      ctx.beginPath();
      ctx.roundRect(tx, ty, tw, 17, 4);
      ctx.fill();
      ctx.fillStyle = "#fffdf3";
      ctx.textAlign = "center";
      ctx.fillText(tag, tx + tw / 2, ty + 12);
    }
    if (!frame && name === actorName) {
      ctx.strokeStyle = "#a64b22";
      ctx.beginPath();
      ctx.moveTo(ax - 4, ay);
      ctx.lineTo(ax + 4, ay);
      ctx.moveTo(ax, ay - 4);
      ctx.lineTo(ax, ay + 4);
      ctx.stroke();
    }
  }
  if (frame) {
    const [x, y] = g.point(frame.arm);
    ctx.strokeStyle = frame.height === "high" ? "#235347" : "#c56b34";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(x, y, 9, 0, Math.PI * 2);
    ctx.moveTo(x - 13, y);
    ctx.lineTo(x + 13, y);
    ctx.moveTo(x, y - 13);
    ctx.lineTo(x, y + 13);
    ctx.stroke();
  }
  $("#caption span").textContent = frame
    ? frame.cue || "准备演出"
    : "拖动纸片设置初始位置";
  $("#boardPrompt").hidden = !pick;
  $("#boardPrompt").textContent = pick
    ? "点击棋盘选择" + (pick === "to" ? "目标位置" : "途经点") + " · Esc 取消"
    : "";
  board.style.cursor = pick
    ? "crosshair"
    : frame
      ? "default"
      : drag
        ? "grabbing"
        : "grab";
}
function mouseMM(e) {
  const r = board.getBoundingClientRect(),
    g = geometry;
  return [
    (e.clientX - r.left - g.left) / g.scale,
    (g.top + g.gh - e.clientY + r.top) / g.scale,
  ];
}
board.onpointerdown = (e) => {
  if (previewMode || !project || !geometry) return;
  const p = mouseMM(e);
  if (pick) {
    try {
      checkStagePoint(p);
      const k = pick;
      edit(() => setRoutePoint(k, p.map(nfmt)));
    } catch (err) {
      status(err.message);
    }
    return;
  }
  for (const [n, a] of Object.entries(project.stage.actors).reverse()) {
    if (
      Math.abs(
        p[0] -
          a.start_mm[0] +
          a.pickup_offset_mm[0] +
          (a.marker_offset_mm?.[0] || 0),
      ) <=
        a.print_size_mm[0] / 2 &&
      Math.abs(
        p[1] -
          a.start_mm[1] +
          a.pickup_offset_mm[1] +
          (a.marker_offset_mm?.[1] || 0),
      ) <=
        a.print_size_mm[1] / 2
    ) {
      actorName = n;
      drag = {
        name: n,
        down: p,
        start: [...a.start_mm],
        snapshot: clone(project),
      };
      board.setPointerCapture(e.pointerId);
      renderSide();
      draw();
      return;
    }
  }
};
board.onpointermove = (e) => {
  if (!drag) return;
  const p = mouseMM(e),
    a = project.stage.actors[drag.name];
  a.start_mm = p.map((n, i) =>
    nfmt(
      Math.max(
        0,
        Math.min(project.stage.size_mm[i], drag.start[i] + n - drag.down[i]),
      ),
    ),
  );
  draw();
};
function endDrag(e, cancel = false) {
  if (!drag) return;
  const d = drag;
  drag = null;
  if (board.hasPointerCapture(e.pointerId))
    board.releasePointerCapture(e.pointerId);
  const point = project.stage.actors[d.name].start_mm;
  const bar = (project.stage.health_bars || []).find((b) =>
    b.tokens.includes(d.name),
  );
  if (bar && !cancel && !inHealthBar(bar, point)) {
    cancel = true;
    status("开场血块须在所属血条区内；演出扣血请使用移动动作。");
  }
  if (cancel) project = d.snapshot;
  else if (point.some((n, i) => n !== d.start[i])) {
    past.push(d.snapshot);
    if (past.length > 25) past.shift();
    future = [];
    changed();
    return;
  }
  render();
}
board.onpointerup = (e) => endDrag(e);
board.onpointercancel = (e) => endDrag(e, true);
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && pick) {
    pick = null;
    draw();
  }
});
new ResizeObserver(draw).observe(board);
$("#showMarkers").onchange = draw;
$("#undo").onclick = () => recover(past, future);
$("#redo").onclick = () => recover(future, past);
$("#actorTab").onclick = () => selectTab("actors");
$("#healthTab").onclick = () => selectTab("health");
$("#reserveTab").onclick = () => selectTab("reserves");
$("#stageTab").onclick = () => selectTab("stage");
$("#modeEdit").onclick = () => {
  intent++;
  editMode();
  draw();
};
$("#modePreview").onclick = () => beginPreview(false);
$("#play").onclick = () => (playing ? pause() : beginPreview(true));
$("#scrub").oninput = async (e) => {
  const ratio = e.target.valueAsNumber / 10000;
  try {
    pause();
    if (!(await ensurePreview())) return;
    previewMode = true;
    pick = null;
    t = preview.duration_s * ratio;
    updateControls();
    draw();
  } catch (err) {
    status(err.message);
  }
};
$("#titleEdit").onclick = titleDialog;
$("#addStep").onclick = addStepDialog;
$("#deployment").onclick = () => modal(
  "部署与标定", deploymentGuide(project.stage.size_mm), saveBtn("打印标定码"),
  () => {
    $("#dialog").close();
    printDialog();
    $("#parts").value = "calibration";
  },
);
$("#print").onclick = printDialog;
$("#newProject").onclick = makeNew;
$("#import").onclick = () => $("#importFile").click();
$("#importFile").onchange = async (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  try {
    await importProject(file);
  } catch (err) {
    status("导入失败：" + err.message);
  }
};
$("#export").onclick = async () => {
  try {
    await api("/api/validate", project);
    download();
  } catch (err) {
    status(err.message);
  }
};
try {
  project = await api("/api/example");
  actorName = Object.keys(project.stage.actors)[0];
  stepIndex = Math.max(
    0,
    project.show.steps.findIndex((s) => s.op === "move"),
  );
  render();
  $("#app").inert = false;
  $("#app").setAttribute("aria-busy", "false");
  document
    .querySelectorAll(".top nav button")
    .forEach((b) => (b.disabled = false));
} catch (err) {
  $("#title").textContent = "剧本载入失败";
  status(err.message);
}
