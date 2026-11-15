// The GTA VI Effect: frontend. No build step, no dependencies.
const SOURCES = ["steam", "github", "wikiedits", "trends", "trending", "appstore", "twitch", "youtube", "tomtom", "radar", "stocks", "twitch_vod", "meta", "status"];
const DATA_URL = "data/";
const HOUR = 3600e3, DAY = 24 * HOUR;
const C = { pink: "#f0428c", cyan: "#1aa5b8", orange: "#d9771f", base: "#8a7a9e", grid: "#34244b", surface: "#1c1030" };

let CHART_W = 360;
let DATA = {}, LAUNCH = Date.parse("2026-11-19T05:00:00Z"), RANGE_DAYS = 3;
try { const r = localStorage.getItem("range"); if (r != null && Number.isFinite(+r)) RANGE_DAYS = +r; } catch { /* storage unavailable */ }
// RANGE_DAYS = 0 means "Since Nov 1st '26": everything from the start of the
// backfilled history (HISTORY_START in collector/config.py).
const HISTORY_START = Date.parse("2026-11-01T00:00:00Z");
const rangeStart = () => RANGE_DAYS ? Date.now() - RANGE_DAYS * DAY : HISTORY_START;

// ---------- utils ----------
const $ = (s, el = document) => el.querySelector(s);
const el = (tag, attrs = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) k === "class" ? (n.className = v) : n.setAttribute(k, v);
  for (const k of kids) if (k != null) n.append(k);
  return n;
};
const svgEl = (tag, attrs = {}) => {
  const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
};
const compact = (v, d = 1) => {
  if (v == null || Number.isNaN(v)) return "–";
  const a = Math.abs(v);
  if (a >= 1e9) return (v / 1e9).toFixed(d) + "B";
  if (a >= 1e6) return (v / 1e6).toFixed(d) + "M";
  if (a >= 1e4) return (v / 1e3).toFixed(d) + "K";
  return Math.round(v).toLocaleString("en-US");
};
const pct = (v, d = 1) => (v == null ? "–" : v.toFixed(d) + "%");
const money = v => (v == null ? "–" : "$" + v.toFixed(2));
const ET = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hour: "numeric", hourCycle: "h23", weekday: "short" });
function etParts(ts) {
  const p = Object.fromEntries(ET.formatToParts(new Date(ts)).map(x => [x.type, x.value]));
  return { hour: +p.hour % 24, weekend: p.weekday === "Sat" || p.weekday === "Sun" };
}
const ordinal = n => n + (n % 100 >= 11 && n % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] || "th");
// "Wed 12th, 11:00 PM" (viewer's local time)
const fmtTime = ts => {
  const d = new Date(ts);
  return `${d.toLocaleString("en-US", { weekday: "short" })} ${ordinal(d.getDate())}, ${d.toLocaleString("en-US", { hour: "numeric", minute: "2-digit" })}`;
};

const series = (src, key) => (DATA[src]?.series?.[key] || []).filter(p => p[1] != null);

function sumSeries(list) {
  const m = new Map();
  for (const s of list) for (const [t, v] of s) m.set(t, (m.get(t) || 0) + v);
  return [...m].sort((a, b) => a[0] - b[0]);
}

// Baseline: mean at the same US-Eastern hour on pre-launch days of the same type.
function baselineFn(pts) {
  // exclude the last 20h so 'now' is compared with earlier days, never itself
  const cutoff = Math.min(LAUNCH, Date.now() - 20 * HOUR);
  const buckets = new Map();
  for (const [t, v] of pts) {
    if (t >= cutoff) continue;
    const { hour, weekend } = etParts(t);
    for (const k of [`${weekend}-${hour}`, `any-${hour}`]) {
      const b = buckets.get(k) || [0, 0]; b[0] += v; b[1]++; buckets.set(k, b);
    }
  }
  const mean = k => { const b = buckets.get(k); return b ? b[0] / b[1] : null; };
  return t => { const { hour, weekend } = etParts(t); return mean(`${weekend}-${hour}`) ?? mean(`any-${hour}`); };
}

function latest(pts, maxAgeH = 8) {
  const p = pts[pts.length - 1];
  return p && Date.now() - p[0] < maxAgeH * HOUR ? p : null;
}

// Relative deviation of the latest point from its baseline.
// `floor` keeps near-zero baselines (e.g. 0.5% congestion at night) from exploding.
function deviation(pts, maxAgeH, floor = 0) {
  const p = latest(pts, maxAgeH);
  if (!p) return null;
  const b = baselineFn(pts)(p[0]);
  if (b == null || (!b && !floor)) return null;
  return (p[1] - b) / Math.max(b, floor);
}

// Points inside the selected range. For market data (`sessions`) the range is the
// last N trading sessions, so weekends and nights never leave an empty chart.
const ET_DATE = new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" });
function inRange(pts, sessions) {
  if (!sessions) return pts.filter(p => p[0] >= rangeStart());
  const all = [...new Set(pts.map(p => ET_DATE.format(p[0])))];
  const days = RANGE_DAYS ? all.slice(-RANGE_DAYS) : all;
  return pts.filter(p => days.includes(ET_DATE.format(p[0])));
}

// Google returns daily values for long windows, normalised differently from the
// hourly week. Scale them onto the hourly series using days covered by both, and
// keep only days before the hourly data starts. Drawn as faded context.
function dailyContext(hourly, daily) {
  if (!hourly.length || !daily.length) return [];
  const dayKey = t => Math.floor(t / DAY);
  const byDay = new Map();
  for (const [t, v] of hourly) { const k = dayKey(t), b = byDay.get(k) || [0, 0]; b[0] += v; b[1]++; byDay.set(k, b); }
  const ratios = daily.map(([t, v]) => { const b = byDay.get(dayKey(t)); return b && b[1] >= 20 && v ? (b[0] / b[1]) / v : null; }).filter(r => r != null);
  if (!ratios.length) return [];
  const k = ratios.reduce((a, b) => a + b, 0) / ratios.length;
  return daily.filter(([t]) => t + DAY <= hourly[0][0]).map(([t, v]) => [t + DAY / 2, Math.round(v * k * 10) / 10]);
}

// Hourly Trends before the current week come from older 7-day windows that Google
// scales differently. They share a day with the current week; rescale them on that
// overlap and join them into one hourly series.
function stitchEarly(hourly, early) {
  if (!hourly.length || !early.length) return hourly;
  const h = new Map(hourly);
  let num = 0, den = 0;
  for (const [t, v] of early) if (h.has(t)) { num += h.get(t); den += v; }
  if (!den) return hourly;
  const k = num / den, start = hourly[0][0];
  return early.filter(([t]) => t < start).map(([t, v]) => [t, Math.round(v * k * 10) / 10]).concat(hourly);
}

// ---------- chart ----------
function lineChart({ main, name, color = C.pink, showBaseline = true, yFmt = compact, step = false, sessions = false, context = [], others = [], invert = false, relative = false }) {
  const W = Math.max(260, Math.round(CHART_W)), H = 150, M = { l: 44, r: 10, t: 10, b: 22 };
  const now = Date.now();
  let x0 = rangeStart();
  const pts = inRange(main, sessions);
  const ctx = sessions ? [] : context.filter(p => p[0] >= rangeStart());
  const svg = svgEl("svg", { class: "chart", viewBox: `0 0 ${W} ${H}`, tabindex: "0", role: "img", "aria-label": `${name}, ${RANGE_DAYS ? RANGE_DAYS + " day" : "since November 1st 2026"} chart` });
  if (pts.length < 2) {
    const t = svgEl("text", { x: W / 2, y: H / 2, "text-anchor": "middle" }); t.textContent = "Collecting data: next point within 30 min"; svg.append(t);
    return svg;
  }
  // Short history (e.g. a snapshot metric tracked for a few hours): zoom the x-axis to
  // the data instead of squeezing it into the right edge of a multi-day axis.
  // "Since Nov 1st" always fits the data; a fixed range zooms (with a note) only when history is shorter.
  const first = Math.min(pts[0][0], ctx.length ? ctx[0][0] : Infinity);
  const fit = !sessions && first > x0 + 2 * HOUR;
  const zoomed = fit && RANGE_DAYS > 0;
  if (fit) x0 = first - Math.max(HOUR / 2, (now - first) * 0.04);
  const bf = baselineFn(main);
  const base = showBaseline ? pts.map(([t]) => [t, bf(t)]).filter(p => p[1] != null) : [];
  const oth = others.map(o => ({ ...o, pts: inRange(o.pts, sessions) }));
  const ys = pts.map(p => p[1]).concat(base.map(p => p[1]), ctx.map(p => p[1]), ...oth.map(o => o.pts.map(p => p[1])));
  let lo = Math.min(...ys), hi = Math.max(...ys);
  const pad = (hi - lo) * 0.1 || Math.abs(hi) * 0.1 || 1; lo -= pad; hi += pad;
  if (lo < 0 && Math.min(...ys) >= 0) lo = 0;
  const x1 = Math.max(now, pts[pts.length - 1][0]);
  // sessions: space points by trading time (closed hours collapsed); otherwise by clock time
  const firstIdx = t => { const i = pts.findIndex(p => p[0] >= t); return i < 0 ? pts.length - 1 : i; };
  const X = sessions
    ? t => M.l + firstIdx(t) / (pts.length - 1) * (W - M.l - M.r)
    : t => M.l + (t - x0) / (x1 - x0) * (W - M.l - M.r);
  const Y = v => M.t + (invert ? (v - lo) / (hi - lo) : 1 - (v - lo) / (hi - lo)) * (H - M.t - M.b);

  // grid + y ticks (3 clean ticks)
  const seenTicks = new Set();
  for (let i = 0; i <= 2; i++) {
    const v = lo + (hi - lo) * i / 2, y = Y(v);
    if (relative) { svg.append(svgEl("line", { x1: M.l, x2: W - M.r, y1: y, y2: y, stroke: C.grid, "stroke-width": 1, "vector-effect": "non-scaling-stroke" })); continue; }
    if (seenTicks.has(yFmt(v))) continue; // tiny ranges would repeat labels
    seenTicks.add(yFmt(v));
    svg.append(svgEl("line", { x1: M.l, x2: W - M.r, y1: y, y2: y, stroke: C.grid, "stroke-width": 1, "vector-effect": "non-scaling-stroke" }));
    const t = svgEl("text", { x: M.l - 6, y: y + 4, "text-anchor": "end" }); t.textContent = yFmt(v); svg.append(t);
  }
  // day ticks
  if (sessions) {
    // one label per trading session, at its first bar
    let lastX = -1e9;
    pts.forEach(([t], i) => {
      if (i && ET_DATE.format(t) === ET_DATE.format(pts[i - 1][0])) return;
      const x = X(t);
      if (i) svg.append(svgEl("line", { x1: x, x2: x, y1: M.t, y2: H - M.b, stroke: C.grid, "stroke-width": 1, "vector-effect": "non-scaling-stroke" }));
      if (x - lastX < 44) return;
      const tx = svgEl("text", { x: Math.min(x + 4, W - M.r - 20), y: H - 6 });
      tx.textContent = new Date(t).toLocaleString("en-US", { weekday: "short", timeZone: "America/New_York" });
      svg.append(tx); lastX = x;
    });
  } else {
  // x ticks at local midnight/6h/12h, spaced >= 56px apart; midnight shows the weekday
  const pxPerH = (W - M.l - M.r) / ((x1 - x0) / HOUR);
  const stepH = [1, 3, 6, 12, 24, 48, 96, 168, 336, 720].find(h => h * pxPerH >= 56) || 720;
  const long = x1 - x0 > 7 * DAY; // past a week, weekday names repeat: label with dates
  const start = new Date(x0); start.setMinutes(0, 0, 0);
  const day0 = new Date(x0); day0.setHours(0, 0, 0, 0);
  for (let t = start.getTime(); t < x1; t += HOUR) {
    const d = new Date(t);
    if (t < x0 || d.getHours() % Math.min(stepH, 24)) continue;
    if (stepH > 24 && Math.round((t - day0.getTime()) / DAY) % (stepH / 24)) continue;
    const x = X(t);
    if (x < M.l + 14 || x > W - M.r - 14) continue;
    const tx = svgEl("text", { x, y: H - 6, "text-anchor": "middle" });
    tx.textContent = d.getHours() !== 0 ? d.toLocaleString("en-US", { hour: "numeric" })
      : d.toLocaleString("en-US", long ? { month: "short", day: "numeric" } : { weekday: "short" });
    svg.append(tx);
  }
  }
  // launch marker
  if (sessions ? LAUNCH > pts[0][0] && LAUNCH < pts[pts.length - 1][0] : LAUNCH > x0 && LAUNCH < x1) {
    const lx = X(LAUNCH);
    svg.append(svgEl("line", { x1: lx, x2: lx, y1: M.t, y2: H - M.b, stroke: C.orange, "stroke-width": 1.5, "vector-effect": "non-scaling-stroke" }));
    const t = svgEl("text", { x: lx + 4, y: M.t + 10 }); t.textContent = "Launch"; t.style.fill = C.orange; svg.append(t);
  }
  const path = (arr, joinGaps = false) => arr.map(([t, v], i) => {
    const prev = arr[i - 1];
    if (!i || (!sessions && !joinGaps && t - prev[0] > 4 * HOUR)) return `M${X(t).toFixed(1)},${Y(v).toFixed(1)}`;
    return step ? `H${X(t).toFixed(1)}V${Y(v).toFixed(1)}` : `L${X(t).toFixed(1)},${Y(v).toFixed(1)}`;
  }).join("");
  const common = { fill: "none", "stroke-linejoin": "round", "stroke-linecap": "round", "vector-effect": "non-scaling-stroke" };
  if (ctx.length) svg.append(svgEl("path", { ...common, d: path([...ctx, pts[0]], true), stroke: color, "stroke-width": 2, opacity: .4 }));
  if (base.length) svg.append(svgEl("path", { ...common, d: path(base), stroke: C.base, "stroke-width": 1.5, opacity: .9 }));
  for (const o of oth) if (o.pts.length) svg.append(svgEl("path", { ...common, d: path(o.pts), stroke: o.color, "stroke-width": 2 }));
  svg.append(svgEl("path", { ...common, d: path(pts), stroke: color, "stroke-width": 2 }));
  const last = pts[pts.length - 1];
  svg.append(svgEl("ellipse", { cx: X(last[0]), cy: Y(last[1]), rx: 4.5, ry: 4.5, fill: color, stroke: C.surface, "stroke-width": 2, class: "enddot" }));

  if (zoomed) {
    const span = (now - pts[0][0]) / HOUR;
    svg.dataset.zoomNote = `Showing all ${span < 48 ? Math.max(1, Math.round(span)) + "h" : Math.round(span / 24) + " days"} tracked so far: the selected range isn't reached yet.`;
  }
  // hover layer
  const cross = svgEl("line", { y1: M.t, y2: H - M.b, stroke: "#d9c8e3", "stroke-width": 1, "vector-effect": "non-scaling-stroke", visibility: "hidden" });
  const dot = svgEl("ellipse", { rx: 4.5, ry: 4.5, fill: color, stroke: C.surface, "stroke-width": 2, visibility: "hidden" });
  svg.append(cross, dot);
  const tip = $("#tip");
  let idx = pts.length - 1;
  const show = (i, clientX, clientY) => {
    idx = Math.max(0, Math.min(pts.length - 1, i));
    const [t, v] = pts[idx];
    cross.setAttribute("x1", X(t)); cross.setAttribute("x2", X(t)); cross.setAttribute("visibility", "visible");
    dot.setAttribute("cx", X(t)); dot.setAttribute("cy", Y(v)); dot.setAttribute("visibility", "visible");
    tip.replaceChildren(el("div", { class: "t" }, fmtTime(t)));
    const row = (c, val, label) => { const i = el("i"); i.style.background = c; tip.append(el("div", { class: "r" }, i, el("b", {}, val), el("span", {}, label))); };
    const bNow = showBaseline ? bf(t) : null;
    const relTxt = bNow ? `${v >= bNow ? "+" : "−"}${Math.abs((v / bNow - 1) * 100).toFixed(0)}% vs normal` : "–";
    row(color, relative ? relTxt : yFmt(v), name);
    for (const o of oth) {
      const q = o.pts.reduce((best, p) => (Math.abs(p[0] - t) < Math.abs((best?.[0] ?? Infinity) - t) ? p : best), null);
      if (q && Math.abs(q[0] - t) < HOUR) row(o.color, yFmt(q[1]), o.name);
    }
    const b = showBaseline ? bf(t) : null;
    if (b != null && !relative) row(C.base, yFmt(b), "normal for this hour");
    tip.hidden = false;
    const r = svg.getBoundingClientRect();
    const cx = clientX ?? r.left + X(t) / W * r.width, cy = clientY ?? r.top;
    const tw = tip.offsetWidth;
    tip.style.left = Math.min(window.innerWidth - tw - 8, Math.max(8, cx + 12)) + "px";
    tip.style.top = Math.max(8, cy - tip.offsetHeight - 12) + "px";
  };
  const hide = () => { tip.hidden = true; cross.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); };
  const nearest = clientX => {
    const r = svg.getBoundingClientRect();
    if (sessions) return Math.round(((clientX - r.left) / r.width * W - M.l) / (W - M.l - M.r) * (pts.length - 1));
    const t = x0 + ((clientX - r.left) / r.width * W - M.l) / (W - M.l - M.r) * (x1 - x0);
    let best = 0; for (let i = 1; i < pts.length; i++) if (Math.abs(pts[i][0] - t) < Math.abs(pts[best][0] - t)) best = i;
    return best;
  };
  svg.addEventListener("pointermove", e => show(nearest(e.clientX), e.clientX, e.clientY));
  svg.addEventListener("pointerleave", hide);
  svg.addEventListener("focus", () => show(idx));
  svg.addEventListener("blur", hide);
  svg.addEventListener("keydown", e => {
    if (e.key === "ArrowLeft") { show(idx - 1); e.preventDefault(); }
    if (e.key === "ArrowRight") { show(idx + 1); e.preventDefault(); }
  });
  return svg;
}

function dataTable(pts, yFmt) {
  const recent = pts.slice(-24).reverse();
  const tb = el("tbody");
  for (const [t, v] of recent) tb.append(el("tr", {}, el("td", {}, fmtTime(t)), el("td", {}, yFmt(v))));
  return el("details", { class: "table" }, el("summary", {}, "Show data"),
    el("div", { class: "scroll" }, el("table", {}, el("thead", {}, el("tr", {}, el("th", {}, "Time"), el("th", {}, "Value"))), tb)));
}

// ---------- cards ----------
// sense: +1 if an increase means "more slacking", -1 if a decrease does.
// Brand logos (official colors) shown next to platform-specific card titles.
const LOGOS = {
  twitch: { color: "#9146FF", vb: "0 0 24 24", d: "M11.571 4.714h1.715v5.143H11.57zm4.715 0H18v5.143h-1.714zM6 0 1.714 4.286v15.428h5.143V24l4.286-4.286h3.428L22.286 12V0zm14.571 11.143-3.428 3.428h-3.429l-3 3v-3H6.857V1.714h13.714Z" },
  google: { vb: "0 0 24 24", paths: [
    ["#4285F4", "M23.49 12.27c0-.79-.07-1.54-.19-2.27H12v4.51h6.47c-.29 1.48-1.14 2.73-2.4 3.58v3h3.86c2.26-2.09 3.56-5.17 3.56-8.82z"],
    ["#34A853", "M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96H1.29v3.09C3.26 21.3 7.31 24 12 24z"],
    ["#FBBC05", "M5.27 14.29c-.25-.72-.38-1.49-.38-2.29s.14-1.57.38-2.29V6.62H1.29C.47 8.24 0 10.06 0 12s.47 3.76 1.29 5.38l3.98-3.09z"],
    ["#EA4335", "M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.7 1.29 6.62l3.98 3.09C6.22 6.86 8.87 4.75 12 4.75z"],
  ] },
  youtube: { color: "#FF0000", vb: "0 0 24 24", d: "M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" },
};
function logo(name) {
  const L = LOGOS[name]; if (!L) return null;
  const s = svgEl("svg", { class: "logo", viewBox: L.vb, width: 16, height: 16, role: "img", "aria-label": name[0].toUpperCase() + name.slice(1) });
  for (const [fill, d] of L.paths || [[L.color, L.d]]) s.append(svgEl("path", { d, fill }));
  return s;
}

function card({ icon, title, headline, pts, fmt = compact, sense = 1, note, wide, chart = true, extra, name, color, step, maxAgeH = 8, showBaseline = true, valueText, floor = 0, sessions = false, snapshot = false, context = [], others = [], invert = false, relative = false, top = null, cash = null }) {
  const c = el("article", { class: "card" + (wide ? " wide" : "") });
  const p = pts && latest(pts, maxAgeH);
  // Sentence headline ("{v} of the top 100 … are about GTA VI") when there's a value; small label otherwise.
  const useHeadline = headline && p;
  if (!useHeadline) c.append(el("p", { class: "label" + (icon ? " with-logo" : "") }, icon ? logo(icon) : null, title));
  if (!p && !extra) {
    c.classList.add("pending");
    c.append(el("div", { class: "stat-row" }, el("span", { class: "value" }, pts?.length ? "Data is stale" : "Coming soon")));
    if (note) c.append(el("p", { class: "note" }, note));
    return c;
  }
  if (p) {
    const relDev = relative ? deviation(pts, maxAgeH, floor) : null;
    const relOk = relDev != null && Number.isFinite(relDev);
    const relText = relOk ? `${Math.abs(relDev * 100).toFixed(0)}%` : "–";
    const relDir = relOk ? (relDev >= 0 ? "above" : "below") : "vs";
    const valueEl = el("span", { class: "value" + (cash ? " cash-value" : "") }, relative ? relText : (valueText ?? fmt(p[1])));
    if (cash) rollUp(valueEl, p[1], fmt, cash);
    let row;
    if (useHeadline) {
      let [before, after] = headline.split("{v}");
      if (relative) after = ` ${relDir}${after}`;
      c.append(el("h3", { class: "headline" + (icon ? " with-logo" : "") }, icon ? logo(icon) : null,
        el("span", {}, before || null, valueEl, after || null)));
      row = el("div", { class: "stat-row" });
    } else {
      row = el("div", { class: "stat-row" }, valueEl);
    }
    const dev = showBaseline && !relative ? deviation(pts, maxAgeH, floor) : null;
    if (dev != null && Number.isFinite(dev)) {
      const up = dev >= 0, slack = (up ? 1 : -1) * sense > 0;
      row.append(el("span", { class: "delta " + (slack ? "slack" : "work") },
        el("span", { class: "arrow", "aria-hidden": "true" }, up ? "▲" : "▼"),
        `${Math.abs(dev * 100).toFixed(Math.abs(dev) < 0.1 ? 1 : 0)}% vs normal`));
    }
    if (row.childNodes.length) c.append(row);
    if (top) c.append(top);
    if (chart) {
      const chartEl = lineChart({ main: pts, name: name || title, color, yFmt: fmt, step, showBaseline, sessions, context, others, invert, relative });
      if (chartEl.dataset.zoomNote) c.append(el("p", { class: "zoom-note" }, chartEl.dataset.zoomNote));
      c.append(chartEl);
      const lg = el("div", { class: "legend" });
      const key = (col, label) => { const i = el("i"); i.style.background = col; lg.append(el("span", {}, i, label)); };
      key(color || C.pink, name || "Now");
      for (const o of others) key(o.color, o.name);
      if (showBaseline) key(C.base, "Normal for that hour");
      if (context.length && context[0][0] >= rangeStart()) { const i = el("i"); i.style.background = color || C.pink; i.style.opacity = .4; lg.append(el("span", {}, i, "Daily (earlier)")); }
      c.append(lg);
      if (!relative) c.append(dataTable(inRange(pts, sessions), fmt));
    }
  }
  if (extra) c.append(extra);
  if (note) c.append(el("p", { class: "note" }, note));
  const first = pts?.[0]?.[0];
  if (snapshot && chart && first && Date.now() - first < Math.min(RANGE_DAYS || 3, 3) * DAY)
    c.append(el("p", { class: "note since" }, `No public archive exists for this metric: tracking since ${fmtTime(first)}, so history builds up from here.`));
  return c;
}

function list(items) {
  const ul = el("ul", { class: "list" });
  for (const [name, num, small] of items) ul.append(el("li", {}, el("span", { class: "name" }, name), el("span", { class: "num" }, num, small ? el("small", {}, small) : null)));
  return ul;
}

// ---------- sections ----------
function renderAttention() {
  const sec = $("#sec-attention"); sec.replaceChildren();
  const tw = DATA.twitch, yt = DATA.youtube, tr = DATA.trending;
  const playing = latest(series("twitch", "global_playing_share"), 8);
  sec.append(card({ icon: "twitch", snapshot: true, title: "Top 100 Twitch streams about GTA VI", headline: "{v} of the top 100 Twitch streams are about GTA VI", pts: series("twitch", "global_stream_share"), fmt: v => pct(v, 0),
    name: "% of top 100 live streams", showBaseline: false,
    note: `The 100 most-watched live streams worldwide whose game or title is GTA VI. Actually playing it: ${playing ? pct(playing[1], 0) : "–"}.` }));
  sec.append(card({ icon: "twitch", snapshot: true, title: "Share of Twitch viewers watching GTA VI", headline: "{v} of top-100 Twitch viewers are watching something related to GTA VI", pts: series("twitch", "global_viewer_share"), fmt: v => pct(v, 1),
    name: "% of top-100 viewers", color: C.cyan, showBaseline: false,
    extra: tw?.meta?.top_gta6_streams_global?.length ? list(tw.meta.top_gta6_streams_global.map(s => [(s.playing ? "🎮 " : "💬 ") + s.user, compact(s.viewers), "viewers"])) : null,
    note: "🎮 playing GTA VI · 💬 mentions it in the title." }));

  // Reconstructed from past broadcasts: its own chart, never spliced into the live metric.
  const vod = DATA.twitch_vod, liveN = new Map(series("twitch_vod", "panel_live").map(([t, n]) => [t, n]));
  const est = series("twitch_vod", "panel_gta_share").filter(([t]) => (liveN.get(t) || 0) >= 100);
  // Estimated big-streamer share (data/twitch_vod.json) is still refreshed every 6h but hidden for now.

  const slots = tr?.meta?.slots || 100, nowHits = latest(series("trending", "world_gta6_items"), 8)?.[1];
  const items = tr?.meta?.gta6_items || [];
  sec.append(card({ icon: "google", snapshot: true, title: "GTA VI in Google Trending Now (10 countries)", headline: "{v} trending Google searches in 10 countries are about GTA VI", pts: series("trending", "world_slot_share"), fmt: v => pct(v, 0),
    name: "% of trending slots", color: C.orange, showBaseline: false, step: true,
    valueText: nowHits != null ? `${nowHits} of ${slots}` : undefined,
    extra: items.length ? list(items.slice(0, 6).map(i => ["🎮 " + i.title, compact(i.traffic) + "+", i.geo])) : (tr ? el("p", { class: "note" }, "No GTA VI searches in any country's top 10 right now.") : null),
    note: `Top-10 trending searches in ${(tr?.meta?.geos || []).join(", ")}: ${slots} slots in total.` }));

  const per = yt?.meta?.per_region || {};
  const regionRow = Object.entries(per).sort((a, b) => b[1] - a[1]).map(([r, v]) => `${r} ${v.toFixed(0)}%`).join(" · ");
  const gaming = latest(series("youtube", "world_gaming_share"), 8)?.[1];
  sec.append(card({ icon: "youtube", snapshot: true, title: "Most-popular YouTube videos about GTA VI (10 countries)", headline: "{v} of the most-popular YouTube videos are about GTA VI", pts: series("youtube", "world_top100_share"), fmt: v => pct(v, 1),
    name: "% of top-100 videos (avg)", showBaseline: false,
    extra: yt?.meta?.top_gta6_videos?.length ? list(yt.meta.top_gta6_videos.slice(0, 5).map(v => [v.title, "", v.regions.join(" ")])) : null,
    note: [regionRow && `By country: ${regionRow}.`, gaming != null && `Gaming category: ${pct(gaming, 1)}.`].filter(Boolean).join(" ") || null }));
  sec.append(card({ title: "Steam users online (global)", headline: "{v} people are online on Steam: does PC gaming dip as players switch to consoles?", pts: series("steam", "logged_in"), sense: -1, name: "Logged in",
    note: "If players switch to their PS5 or Xbox, Steam should dip." }));
  sec.append(card({ title: "GTA V players on Steam", headline: "{v} people are still playing GTA V on Steam", pts: series("steam", "gtav_players"), sense: -1, name: "Concurrent players", color: C.cyan,
    note: "Does the old game empty out?" }));
}

function renderWork() {
  const sec = $("#sec-work"); sec.replaceChildren();
  sec.append(card({ title: "GitHub pull requests opened / hour", headline: "{v} GitHub pull requests opened in the last hour", pts: series("github", "prs_per_hour"), sense: -1, name: "PRs per hour", step: true, maxAgeH: 4,
    note: "Global developer output. Are devs shipping or playing?" }));
  // Wikipedia edits are still collected (data/wikiedits.json) but hidden from the page.
  const sickTerms = ["call in sick", "sick day"];
  const sick = sumSeries(sickTerms.map(k => series("trends", `sick:${k}`)));
  const sickAll = stitchEarly(sick, sumSeries(sickTerms.map(k => series("trends", `sick:${k}:early`))));
  sec.append(card({ title: "US searches: “call in sick” + “sick day”", headline: "Searches for calling in sick are {v} normal for this time of day", relative: true, pts: sickAll, sense: 1, name: "Searches", color: C.orange, maxAgeH: 4,
    note: "Compared with the same hour on normal days (weekday vs weekday). Google Trends only gives relative interest, not search counts. Older weeks are stitched from overlapping 7-day windows, so their scale is approximate." }));
  // Commuting and internet use (formerly "Roads & wires")
  // Freeway congestion (TomTom) is still collected (data/tomtom.json) but hidden for now.
  sec.append(card({ title: "US internet traffic (Cloudflare)", headline: "US internet traffic is at {v} of its range since Nov 1", pts: series("radar", "us_netflows"), sense: 1, fmt: v => pct(v * 100, 0), name: "Traffic (normalised)", color: C.cyan, maxAgeH: 6,
    note: "Normalised volume of US network traffic. GTA VI downloads are 100GB+ per console." }));
  // Food searches (formerly the "Food delivery" section)
  const terms = DATA.trends?.meta?.batches?.food || ["food near me", "pizza near me", "delivery near me"];
  const food = sumSeries(terms.map(k => series("trends", `food:${k}`)));
  const foodAll = stitchEarly(food, sumSeries(terms.map(k => series("trends", `food:${k}:early`))));
  sec.append(card({ headline: "Searches for food are {v} normal for this time of day", relative: true, title: "US ordering-intent searches", pts: foodAll, sense: 1, name: "Searches", color: C.orange, maxAgeH: 4,
    note: `Google Trends for ${terms.map(t => `\u201c${t}\u201d`).join(", ")}: what people type when they're about to order. Compared with the same hour on normal days; Google gives relative interest only, not counts.` }));
  // Delivery-app App Store ranks (data/appstore.json) are still collected but hidden for now.
}



// Rolls a number up from 0 when its element scrolls into view (once per page load per key).
const rolled = new Set();
function rollUp(node, target, fmt, key) {
  if (rolled.has(key) || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
    rolled.add(key); node.textContent = fmt(target); return;
  }
  node.textContent = fmt(0);
  const roll = () => {
    rolled.add(key);
    const t0 = performance.now(), dur = 1600;
    const tick = now => {
      const k = Math.min(1, (now - t0) / dur);
      node.textContent = fmt(target * (1 - Math.pow(1 - k, 3)));
      if (k < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };
  if (!("IntersectionObserver" in window)) return roll();
  const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { io.disconnect(); roll(); } }, { threshold: 0.6 });
  io.observe(node);
}

function renderMarket() {
  const sec = $("#sec-market"); sec.replaceChildren();
  const stocks = [
    ["TTWO", "Take-Two Interactive (TTWO)", C.pink, "GTA's publisher."],
    ["SONY", "Sony (SONY)", C.cyan, "PlayStation 5 maker."],
    ["MSFT", "Microsoft (MSFT)", C.orange, "Xbox maker; gaming is a small slice of its business."],
  ];
  for (const [sym, title, color, blurb] of stocks) {
    const d = latest(series("stocks", `${sym}:pct`), 96)?.[1];
    sec.append(card({ title, headline: `${title.split(" (")[0]} shares at {v}`, cash: sym, pts: series("stocks", `${sym}:price`), fmt: money, showBaseline: false, maxAgeH: 96, name: "Share price (USD)", color, sessions: true,
      extra: d != null ? el("p", { class: "note" }, `Last session: ${d >= 0 ? "+" : ""}${d.toFixed(2)}%`) : null, note: `${blurb} Trading hours only; nights and weekends are collapsed.` }));
  }
}

// ---------- hero ----------
function renderClock() {
  const d = LAUNCH - Date.now(), a = Math.abs(d);
  const days = Math.floor(a / DAY), h = Math.floor(a % DAY / HOUR), m = Math.floor(a % HOUR / 60e3), s = Math.floor(a % 60e3 / 1e3);
  $("#clock-label").textContent = d > 0 ? "Launch countdown" : "Time since launch";
  $("#clock").textContent = (d > 0 ? "" : "T+ ") + (days ? `${days}d ` : "") + `${String(h).padStart(2, "0")}h ${String(m).padStart(2, "0")}m ${String(s).padStart(2, "0")}s`;
  $("#launch-local").textContent = "Launch: " + new Date(LAUNCH).toLocaleString(undefined, { weekday: "long", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" });
}

// ---------- boot ----------
// Charts are drawn at their real pixel width so text never stretches.
function setChartWidth(sec) {
  const cols = getComputedStyle(sec).gridTemplateColumns.split(" ").length || 1;
  CHART_W = (sec.clientWidth - 16 * (cols - 1)) / cols - 36; // minus gaps + card padding
}

function renderAll() {
  setChartWidth($("#sec-work"));
  renderWork(); renderAttention(); renderMarket();
  const gen = DATA.meta?.generated;
  $("#updated").textContent = gen ? `Updated ${new Date(gen).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}` : "";
  const st = DATA.status || {};
  const ok = Object.values(st).filter(x => x.state === "ok").length;
  $("#status-line").textContent = Object.keys(st).length ? `Sources healthy: ${ok}/${Object.keys(st).length}` : "";
}

async function load() {
  document.body.classList.add("loading");
  const results = await Promise.all(SOURCES.map(s =>
    fetch(`${DATA_URL}${s}.json?t=${Math.floor(Date.now() / 300e3)}`).then(r => (r.ok ? r.json() : null)).catch(() => null)));
  DATA = Object.fromEntries(SOURCES.map((s, i) => [s, results[i]]).filter(([, v]) => v));
  if (DATA.meta?.launch) LAUNCH = Date.parse(DATA.meta.launch);
  document.body.classList.remove("loading");
  renderAll();
}

function initRange() {
  const btns = [...document.querySelectorAll("#range button")];
  const sync = () => btns.forEach(b => b.setAttribute("aria-checked", String(+b.dataset.days === RANGE_DAYS)));
  btns.forEach(b => b.addEventListener("click", () => {
    RANGE_DAYS = +b.dataset.days; sync();
    try { localStorage.setItem("range", RANGE_DAYS); } catch { /* ignore */ }
    renderAll();
  }));
  sync();
}

initRange();

// Wanted-level stars beside each section heading: section N shows N of 5 filled.
function addWantedStars() {
  const STAR = "M12 1.8l2.9 6.6 7.1.7-5.4 4.8 1.6 7-6.2-3.7-6.2 3.7 1.6-7L2 9.1l7.1-.7z";
  document.querySelectorAll("main section > h2").forEach((h2, i) => {
    if (h2.previousElementSibling?.classList.contains("wanted")) return;
    const level = Math.min(5, i + 1);
    const box = el("span", { class: "wanted", role: "img", "aria-label": `Wanted level ${level} of 5` });
    for (let k = 0; k < 5; k++) {
      const svg = svgEl("svg", { viewBox: "0 0 24 24", "aria-hidden": "true", class: k < level ? "on" : "off" });
      svg.append(svgEl("path", { d: STAR }));
      box.append(svg);
    }
    h2.before(box); // stars sit above the section title
  });
}
addWantedStars();
let rz; window.addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => DATA.meta && renderAll(), 200); });
renderClock(); setInterval(renderClock, 1000);
load(); setInterval(load, 5 * 60e3);
