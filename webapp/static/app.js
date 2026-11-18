"use strict";

// ---------------------------------------------------------------- utils
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const fmt = (v, d = 2) => (v === null || v === undefined || Number.isNaN(v) ? "—" : Number(v).toFixed(d));
const pct = (v, d = 1) => (v === null || v === undefined ? "—" : (v * 100).toFixed(d) + "%");
const int = (v) => (v === null || v === undefined ? "—" : Number(v).toLocaleString());
const signCls = (v) => (v > 0 ? "pos" : v < 0 ? "neg" : "");

async function api(url, options = {}) {
  const res = await fetch(url, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : `HTTP ${res.status}`);
  return body;
}

function setStatus(el, text, isError = false) {
  el.textContent = text;
  el.classList.toggle("error", isError);
}

function kpi(label, value, sub = "", main = false) {
  return `<div class="kpi${main ? " main" : ""}"><div class="label">${label}</div><div class="value">${value}</div>${sub ? `<div class="sub">${sub}</div>` : ""}</div>`;
}

// Series colours: blue, orange, green, purple — readable in both themes.
const SERIES = ["#3b7cf6", "#f08c2e", "#1fa67a", "#9b6cf0", "#e0517a", "#7c8a9e"];

function baseLayout(extra = {}) {
  const grid = css("--border");
  const text = css("--muted");
  return {
    margin: { l: 56, r: 16, t: 8, b: 44 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "Inter, 'Noto Sans TC', sans-serif", size: 12, color: text },
    xaxis: { gridcolor: grid, zerolinecolor: grid, linecolor: grid },
    yaxis: { gridcolor: grid, zerolinecolor: grid, linecolor: grid },
    legend: { orientation: "h", y: 1.12, x: 0 },
    hovermode: "x unified",
    hoverlabel: { bgcolor: css("--panel"), bordercolor: grid, font: { color: css("--text") } },
    ...extra,
  };
}

function plot(el, traces, layout) {
  Plotly.react(el, traces, baseLayout(layout), { displaylogo: false, responsive: true, modeBarButtonsToRemove: ["lasso2d", "select2d"] });
}

// ---------------------------------------------------------------- theme + tabs
const themeKey = "optionlab-theme";
function applyTheme(theme) {
  if (theme) document.documentElement.dataset.theme = theme;
  else delete document.documentElement.dataset.theme;
}
try { applyTheme(localStorage.getItem(themeKey)); } catch (_) { /* storage unavailable */ }

$("#theme-toggle").addEventListener("click", () => {
  const dark = document.documentElement.dataset.theme
    ? document.documentElement.dataset.theme === "dark"
    : matchMedia("(prefers-color-scheme: dark)").matches;
  const next = dark ? "light" : "dark";
  applyTheme(next);
  try { localStorage.setItem(themeKey, next); } catch (_) { /* ignore */ }
  redrawAll();
});

$$(".tab").forEach((tab) =>
  tab.addEventListener("click", () => {
    $$(".tab").forEach((t) => t.classList.toggle("active", t === tab));
    $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${tab.dataset.view}`));
    window.dispatchEvent(new Event("resize")); // let Plotly size hidden charts
  })
);

$$(".seg").forEach((seg) =>
  seg.addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    $$("button", seg).forEach((b) => b.classList.toggle("on", b === btn));
    seg.dispatchEvent(new Event("change", { bubbles: true }));
  })
);
const segValue = (form, name) => $(`.seg[data-name="${name}"] .on`, form).dataset.value;

// ---------------------------------------------------------------- calculator
const calcForm = $("#calc-form");
let calcData = null;
let calcTimer = null;

async function runCalc() {
  const f = new FormData(calcForm);
  const num = (k) => parseFloat(f.get(k));
  const payload = {
    S: num("S"), K: num("K"), sigma: num("sigma") / 100, T: Math.max(num("days"), 0) / 365,
    r: num("r") / 100, q: num("q") / 100, ratio: num("ratio") || 1,
    kind: segValue(calcForm, "kind"), model: segValue(calcForm, "model"), style: segValue(calcForm, "style"),
  };
  if (!(payload.S > 0 && payload.K > 0 && payload.sigma > 0)) return;
  try {
    calcData = { payload, result: await api("/api/calc", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }) };
    drawCalc();
  } catch (err) {
    $("#calc-kpis").innerHTML = `<div class="kpi"><div class="label">錯誤</div><div class="value neg" style="font-size:14px">${err.message}</div></div>`;
  }
}

function drawCalc() {
  if (!calcData) return;
  const { payload: p, result: r } = calcData;
  const g = r.greeks;
  const modelName = p.model === "crr" ? `CRR ${p.style === "american" ? "美式" : "歐式"}` : "Black-Scholes";
  const timeValue = r.price - r.intrinsic;
  $("#calc-kpis").innerHTML = [
    kpi("理論價格", fmt(r.price, 4), modelName, true),
    kpi("時間價值", fmt(timeValue, 4), `內含價值 ${fmt(r.intrinsic, 4)}`),
    kpi("Delta", fmt(g.delta, 4)),
    kpi("Gamma", fmt(g.gamma, 5)),
    kpi("Theta / 日", fmt(g.theta_per_day, 4)),
    kpi("Vega / 1%", fmt(g.vega, 4)),
    kpi("Rho / 1%", fmt(g.rho, 4)),
  ].join("");

  const c = r.curves;
  const vline = { type: "line", x0: p.S, x1: p.S, yref: "paper", y0: 0, y1: 1, line: { color: css("--muted"), dash: "dot", width: 1 } };
  plot($("#calc-chart"), [
    { x: c.spot, y: c.now, name: "目前價值", line: { color: SERIES[0], width: 2.5 } },
    { x: c.spot, y: c.half, name: "剩一半時間", line: { color: SERIES[1], width: 2 } },
    { x: c.spot, y: c.payoff, name: "到期損益", line: { color: SERIES[5], width: 1.5, dash: "dash" } },
  ], { shapes: [vline], xaxis: { title: "標的價格", gridcolor: css("--border") }, yaxis: { title: "價格", gridcolor: css("--border") } });

  plot($("#calc-greeks-chart"), [
    { x: c.spot, y: c.delta, name: "Delta（選擇權）", line: { color: SERIES[0], width: 2 } },
    { x: c.spot, y: c.gamma, name: "Gamma（選擇權）", yaxis: "y2", line: { color: SERIES[3], width: 2 } },
  ], {
    shapes: [vline],
    xaxis: { title: "標的價格", gridcolor: css("--border") },
    yaxis: { title: "Delta", gridcolor: css("--border") },
    yaxis2: { title: "Gamma", overlaying: "y", side: "right", showgrid: false },
    margin: { l: 56, r: 56, t: 8, b: 44 },
  });
}

calcForm.addEventListener("input", () => { clearTimeout(calcTimer); calcTimer = setTimeout(runCalc, 150); });
calcForm.addEventListener("change", runCalc);
calcForm.addEventListener("submit", (e) => e.preventDefault());

// ---------------------------------------------------------------- US options
const usForm = $("#us-form");
const us = { data: null, selected: null, strategy: null, risk: null, surface: null };
const STRATEGY_ZH = {
  "Single Option": "單一合約", "Long Straddle": "買進跨式", "Short Straddle": "賣出跨式",
  "Long Strangle": "買進勒式", "Short Strangle": "賣出勒式", "Long Call Butterfly": "買進 Call 蝶式",
  "Short Call Butterfly": "賣出 Call 蝶式", "Long Put Butterfly": "買進 Put 蝶式", "Short Put Butterfly": "賣出 Put 蝶式",
  "Bull Call Spread": "Call 多頭價差", "Bear Put Spread": "Put 空頭價差", "Ratio Call Spread": "Call 比例價差",
  "Short Iron Condor": "賣出鐵兀鷹", "Long Iron Condor": "買進鐵兀鷹", "Custom": "自訂",
};
const usParams = () => {
  const f = new FormData(usForm);
  return { ticker: f.get("ticker").trim().toUpperCase(), r: parseFloat(f.get("r")) / 100, q: parseFloat(f.get("q")) / 100 };
};

$$(".subtab").forEach((t) => t.addEventListener("click", () => {
  $$(".subtab").forEach((x) => x.classList.toggle("active", x === t));
  $$("#view-us .sub").forEach((s) => s.classList.toggle("active", s.dataset.sub === t.dataset.sub));
  window.dispatchEvent(new Event("resize"));
}));

async function loadUS(e) {
  e?.preventDefault();
  const p = usParams();
  const params = new URLSearchParams({ ticker: p.ticker, r: p.r, q: p.q });
  const exp = usForm.elements.expiration.value;
  if (exp && us.data && us.data.ticker === p.ticker) params.set("expiration", exp);
  const btn = $("button[type=submit]", usForm);
  btn.disabled = true;
  setStatus($("#us-status"), "從 yfinance 下載中…");
  try {
    const prevTicker = us.data?.ticker;
    us.data = await api(`/api/us/chain?${params}`);
    if (prevTicker !== us.data.ticker) { us.surface = null; Plotly.purge($("#us-surface")); }
    const sel = usForm.elements.expiration;
    sel.innerHTML = us.data.expirations.map((x) => `<option ${x === us.data.expiration ? "selected" : ""}>${x}</option>`).join("");
    const strat = $("#us-strategy-select");
    if (!strat.options.length) strat.innerHTML = us.data.strategies.map((s) => `<option value="${s}">${STRATEGY_ZH[s] || s}</option>`).join("");
    // Default selection: ATM call, kept if the strike still exists.
    const strikes = us.data.calls.map((r) => r.strike);
    if (!us.selected || !strikes.includes(us.selected.strike)) {
      const atm = strikes.reduce((b, k) => (Math.abs(k - us.data.spot) < Math.abs(b - us.data.spot) ? k : b), strikes[0]);
      us.selected = { kind: "call", strike: atm };
    }
    setStatus($("#us-status"), `${us.data.ticker} · ${us.data.expiration} · 更新於 ${new Date().toLocaleTimeString()}`);
    drawUS();
  } catch (err) {
    setStatus($("#us-status"), err.message, true);
  } finally {
    btn.disabled = false;
  }
}

function drawSelected() {
  const s = us.selected;
  $("#us-selected").innerHTML = s && us.data ? `選定合約：<b>${us.data.ticker} ${us.data.expiration} ${s.kind === "call" ? "Call" : "Put"} ${fmt(s.strike)}</b>` : "";
  $$("#us-chain td.pick").forEach((td) => td.classList.toggle("chosen", !!s && td.dataset.kind === s.kind && Number(td.dataset.strike) === s.strike));
}

function drawUS() {
  if (!us.data) return;
  const d = us.data, sm = d.smile || {};
  const days = Math.round(d.T * 365);
  $("#us-kpis").innerHTML = [
    kpi("標的價格", fmt(d.spot, 2), d.ticker, true),
    kpi("Forward（買賣權平價）", fmt(d.forward, 2)),
    kpi("歷史波動率", pct(d.hist_vol), "Newey-West，10 年"),
    kpi("VIX / SVIX", sm.vix !== null && sm.vix !== undefined ? `${fmt(sm.vix, 1)} / ${fmt(sm.svix, 1)}` : "—", sm.vix_error ? "此到期日資料不足" : `差 ${fmt((sm.vix ?? 0) - (sm.svix ?? 0), 2)}`),
    kpi("到期", d.expiration, `${days} 天`),
  ].join("");

  const near = (rows) => rows.filter((r) => r.strike > d.spot * 0.6 && r.strike < d.spot * 1.4);
  const calls = near(d.calls), puts = near(d.puts);
  const fwd = d.forward || d.spot;
  const otmCalls = calls.filter((r) => r.strike >= fwd), otmPuts = puts.filter((r) => r.strike <= fwd);
  const traces = [
    { x: otmPuts.map((r) => r.strike), y: otmPuts.map((r) => r.iv), name: "自算 IV · Put", mode: "markers", marker: { color: SERIES[1], size: 6 } },
    { x: otmCalls.map((r) => r.strike), y: otmCalls.map((r) => r.iv), name: "自算 IV · Call", mode: "markers", marker: { color: SERIES[0], size: 6 } },
    { x: [...otmPuts, ...otmCalls].map((r) => r.strike), y: [...otmPuts, ...otmCalls].map((r) => r.yf_iv), name: "yfinance IV", mode: "markers", marker: { color: SERIES[5], size: 5, symbol: "x" } },
  ];
  if (sm.svi) traces.push({ x: sm.svi.strikes, y: sm.svi.iv, name: "SVI 擬合", mode: "lines", line: { color: SERIES[2], width: 2.5 } });
  $("#us-smile-hint").textContent = sm.svi ? `SVI 擬合 RMSE ${pct(sm.svi.rmse, 2)} · 虛線為 Forward` : `SVI 擬合失敗：${sm.svi_error || "資料不足"}`;
  plot($("#us-smile"), traces, {
    shapes: [{ type: "line", x0: fwd, x1: fwd, yref: "paper", y0: 0, y1: 1, line: { color: css("--muted"), dash: "dot", width: 1 } }],
    xaxis: { title: "履約價", gridcolor: css("--border") },
    yaxis: { title: "隱含波動率", tickformat: ".0%", gridcolor: css("--border") },
  });

  const strikes = [...new Set([...calls, ...puts].map((r) => r.strike))].sort((a, b) => a - b);
  const byStrike = (rows) => Object.fromEntries(rows.map((r) => [r.strike, r]));
  const C = byStrike(calls), P = byStrike(puts);
  const atm = strikes.reduce((best, k) => (Math.abs(k - d.spot) < Math.abs(best - d.spot) ? k : best), strikes[0]);
  const side = (r, itm, order, kind, k) => {
    const cells = r
      ? { iv: pct(r.iv), delta: fmt(r.delta, 3), bid: fmt(r.bid), ask: fmt(r.ask), vol: int(r.volume), oi: int(r.open_interest) }
      : { iv: "—", delta: "—", bid: "—", ask: "—", vol: "—", oi: "—" };
    return order.map((c) => `<td class="${itm ? "itm" : ""} ${r ? "pick" : ""}" data-kind="${kind}" data-strike="${k}">${cells[c]}</td>`).join("");
  };
  const callOrder = ["oi", "vol", "iv", "delta", "bid", "ask"];
  const putOrder = ["bid", "ask", "delta", "iv", "vol", "oi"];
  const head = (o) => o.map((k) => `<th>${{ oi: "未平倉", vol: "量", iv: "IV", delta: "Δ", bid: "買價", ask: "賣價" }[k]}</th>`).join("");
  $("#us-chain").innerHTML =
    `<thead><tr><th colspan="6" style="text-align:center">CALLS</th><th class="strike"></th><th colspan="6" style="text-align:center">PUTS</th></tr>` +
    `<tr>${head(callOrder)}<th class="strike">履約價</th>${head(putOrder)}</tr></thead><tbody>` +
    strikes.map((k) => `<tr class="${k === atm ? "atm" : ""}">${side(C[k], k < d.spot, callOrder, "call", k)}<td class="strike">${fmt(k)}</td>${side(P[k], k > d.spot, putOrder, "put", k)}</tr>`).join("") +
    "</tbody>";
  const atmRow = $("#us-chain tr.atm");
  const wrap = $("#us-chain").parentElement;
  if (atmRow) wrap.scrollTop = atmRow.offsetTop - wrap.clientHeight / 2;
  drawSelected();
  if (us.surface) drawSurface();
}

$("#us-chain").addEventListener("click", (e) => {
  const td = e.target.closest("td.pick");
  if (!td) return;
  us.selected = { kind: td.dataset.kind, strike: Number(td.dataset.strike) };
  drawSelected();
});

// ---- IV surface
async function loadSurface() {
  if (!us.data) return setStatus($("#us-surface-status"), "請先載入代號", true);
  const p = usParams();
  const n = parseInt($("#us-surface-n").value, 10) || 8;
  $("#us-surface-load").disabled = true;
  setStatus($("#us-surface-status"), `下載 ${n} 個到期日中…`);
  try {
    us.surface = await api(`/api/us/surface?${new URLSearchParams({ ticker: p.ticker, r: p.r, q: p.q, max_expirations: n })}`);
    setStatus($("#us-surface-status"), `${us.surface.nodes.length} 個節點`);
    drawSurface();
  } catch (err) {
    setStatus($("#us-surface-status"), err.message, true);
  } finally {
    $("#us-surface-load").disabled = false;
  }
}

function drawSurface() {
  const nodes = us.surface?.nodes || [];
  if (!nodes.length) return;
  const days = [...new Set(nodes.map((n) => n.days))].sort((a, b) => a - b);
  const strikes = [...new Set(nodes.map((n) => n.strike))].sort((a, b) => a - b);
  const key = (d, k) => `${d}|${k}`;
  const map = new Map(nodes.map((n) => [key(n.days, n.strike), n.iv]));
  // Fill gaps by linear interpolation along strike within each expiry.
  const z = days.map((d) => {
    const row = strikes.map((k) => map.get(key(d, k)) ?? null);
    const known = row.map((v, i) => [i, v]).filter(([, v]) => v !== null);
    return row.map((v, i) => {
      if (v !== null || known.length < 2) return v;
      const lo = [...known].reverse().find(([j]) => j < i), hi = known.find(([j]) => j > i);
      if (!lo || !hi) return null;
      return lo[1] + ((hi[1] - lo[1]) * (i - lo[0])) / (hi[0] - lo[0]);
    });
  });
  const axis = { gridcolor: css("--border"), backgroundcolor: "rgba(0,0,0,0)", color: css("--muted") };
  plot($("#us-surface"), [{
    type: "surface", x: strikes, y: days, z, colorscale: "Viridis", showscale: true,
    colorbar: { tickformat: ".0%", len: 0.7 },
    hovertemplate: "履約價 %{x}<br>%{y} 天<br>IV %{z:.1%}<extra></extra>",
  }], {
    margin: { l: 0, r: 0, t: 0, b: 0 }, hovermode: "closest",
    scene: { xaxis: { ...axis, title: "履約價" }, yaxis: { ...axis, title: "剩餘天數" }, zaxis: { ...axis, title: "IV", tickformat: ".0%" }, camera: { eye: { x: 1.6, y: -1.6, z: 0.9 } } },
  });
  $("#us-surface-hint").textContent = `${us.surface.ticker} · ${days.length} 個到期日 · 價外合約自算 IV`;
}
$("#us-surface-load").addEventListener("click", loadSurface);

// ---- strategy backtest
const stratForm = $("#us-strategy-form");
function syncStrategyInputs() {
  const s = $("#us-strategy-select").value;
  $("#us-width-label").hidden = s === "Single Option" || s === "Custom" || s.includes("Straddle");
  $("#us-ratio-label").hidden = s !== "Ratio Call Spread";
  $("#us-custom").hidden = s !== "Custom";
}
$("#us-strategy-select").addEventListener("change", syncStrategyInputs);

function parseCustomLegs(text) {
  return text.split("\n").map((l) => l.trim()).filter(Boolean).map((line, i) => {
    const [option_kind, side, strike, premium, quantity] = line.split(",").map((x) => x.trim());
    if (!["call", "put"].includes(option_kind) || !["long", "short"].includes(side)) throw new Error(`第 ${i + 1} 行格式錯誤：${line}`);
    return { option_kind, side, strike: Number(strike), premium: Number(premium), quantity: Number(quantity || 1) };
  });
}

async function runStrategy(e) {
  e?.preventDefault();
  if (!us.data || !us.selected) return setStatus($("#us-strategy-status"), "請先在「報價與微笑」載入代號並選定合約", true);
  const f = new FormData(stratForm);
  const p = usParams();
  const body = {
    ...p, expiration: us.data.expiration, kind: us.selected.kind, strike: us.selected.strike,
    strategy: f.get("strategy"), width: f.get("width") ? Number(f.get("width")) : null,
    ratio_quantity: Number(f.get("ratio_quantity") || 2), holding_days: Number(f.get("holding_days")),
    initial_capital: Number(f.get("initial_capital")), multiplier: Number(f.get("multiplier")),
    commission: Number(f.get("commission")), slippage: Number(f.get("slippage")), non_overlapping: f.get("non_overlapping") === "on",
  };
  const btn = $("button[type=submit]", stratForm);
  try {
    if (body.strategy === "Custom") body.custom_legs = parseCustomLegs(f.get("custom"));
    btn.disabled = true;
    setStatus($("#us-strategy-status"), "回測中…");
    us.strategy = await api("/api/us/strategy", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    setStatus($("#us-strategy-status"), `${STRATEGY_ZH[body.strategy]} · ${us.strategy.backtest.length} 筆交易`);
    $("#us-strategy-out").hidden = false;
    drawStrategy();
  } catch (err) {
    setStatus($("#us-strategy-status"), err.message, true);
  } finally {
    btn.disabled = false;
  }
}
stratForm.addEventListener("submit", runStrategy);

function drawStrategy() {
  const s = us.strategy;
  if (!s) return;
  const m = s.metrics;
  $("#us-strategy-kpis").innerHTML = [
    kpi("總損益", `<span class="${signCls(m.total_pnl)}">${fmt(m.total_pnl, 0)}</span>`, `平均每筆 ${fmt(m.avg_pnl, 1)}`, true),
    kpi("勝率", pct(m.win_rate)),
    kpi("Sharpe", fmt(m.sharpe_ratio, 2)),
    kpi("最大回撤", `<span class="neg">${fmt(m.mdd, 0)}</span>`, pct(m.mdd_pct)),
    kpi("資本報酬率", pct(m.return_on_capital)),
    kpi("期末權益", fmt(m.ending_equity, 0)),
    kpi("保證金估計", fmt(m.margin_estimate, 0)),
    kpi("VaR / ES 95%", `${fmt(m.var_95_amount, 0)} / ${fmt(m.expected_shortfall_95_amount, 0)}`),
  ].join("");

  $("#us-legs-hint").textContent = `淨權利金 ${fmt(s.net_premium, 2)}（正為付出）· 定價波動率 ${pct(s.sigma)}（${s.sigma_source}）`;
  $("#us-legs").innerHTML = "<thead><tr><th class='text'>類型</th><th class='text'>方向</th><th>履約價</th><th>權利金</th><th>買價</th><th>賣價</th><th>數量</th></tr></thead><tbody>" +
    s.legs.map((l) => `<tr><td class="text"><span class="tag ${l.option_kind}">${l.option_kind === "call" ? "Call" : "Put"}</span></td><td class="text ${l.side === "long" ? "pos" : "neg"}">${l.side === "long" ? "買進" : "賣出"}</td><td>${fmt(l.strike)}</td><td>${fmt(l.premium)}</td><td>${fmt(l.bid)}</td><td>${fmt(l.ask)}</td><td>${int(l.quantity)}</td></tr>`).join("") + "</tbody>";
  const g = s.greeks;
  $("#us-strategy-greeks").innerHTML = [
    kpi("淨 Delta", fmt(g.delta, 3)), kpi("淨 Gamma", fmt(g.gamma, 4)), kpi("淨 Theta/日", fmt(g.theta_per_day, 3)),
    kpi("淨 Vega", fmt(g.vega, 3)), kpi("淨 Rho", fmt(g.rho, 3)),
  ].join("");

  const profit = s.payoff.profit;
  plot($("#us-payoff"), [
    { x: s.payoff.spot, y: profit.map((v) => (v >= 0 ? v : null)), name: "獲利", mode: "lines", fill: "tozeroy", line: { color: css("--up"), width: 2 }, connectgaps: false },
    { x: s.payoff.spot, y: profit.map((v) => (v <= 0 ? v : null)), name: "虧損", mode: "lines", fill: "tozeroy", line: { color: css("--down"), width: 2 }, connectgaps: false },
  ], {
    showlegend: false,
    shapes: [{ type: "line", x0: s.spot, x1: s.spot, yref: "paper", y0: 0, y1: 1, line: { color: css("--muted"), dash: "dot", width: 1 } }],
    xaxis: { title: "到期時標的價格", gridcolor: css("--border") }, yaxis: { title: "每單位損益", gridcolor: css("--border") },
  });

  const bt = s.backtest, x = bt.map((r) => r.exit_date);
  plot($("#us-backtest"), [
    { type: "bar", x, y: bt.map((r) => r.strategy_profit), name: "單筆損益", marker: { color: bt.map((r) => (r.strategy_profit >= 0 ? css("--up") : css("--down"))) } },
    { x, y: bt.map((r) => r.cumulative_pnl), name: "累積損益", mode: "lines", line: { color: SERIES[0], width: 2.5 } },
    { x, y: bt.map((r) => r.entry_sigma), name: "進場波動率", yaxis: "y2", mode: "lines", line: { color: SERIES[5], width: 1, dash: "dot" } },
  ], {
    yaxis: { title: "損益", gridcolor: css("--border") },
    yaxis2: { title: "波動率", overlaying: "y", side: "right", showgrid: false, tickformat: ".0%" },
    margin: { l: 64, r: 56, t: 8, b: 44 },
  });
}

// ---- risk
async function runRisk() {
  if (!us.data || !us.selected) return setStatus($("#us-risk-status"), "請先在「報價與微笑」載入代號並選定合約", true);
  const useStrategy = $("#us-risk-use-strategy").checked;
  if (useStrategy && !us.strategy) return setStatus($("#us-risk-status"), "請先執行策略回測", true);
  const p = usParams();
  const body = {
    ...p, expiration: us.data.expiration, kind: us.selected.kind, strike: us.selected.strike,
    holding_days: Number($("#us-risk-days").value) || 20, multiplier: Number(stratForm.elements.multiplier.value) || 100,
    legs: useStrategy ? us.strategy.legs.map(({ option_kind, side, strike, quantity }) => ({ option_kind, side, strike, quantity })) : null,
  };
  $("#us-risk-run").disabled = true;
  setStatus($("#us-risk-status"), "計算中…");
  try {
    us.risk = await api("/api/us/risk", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    setStatus($("#us-risk-status"), `${useStrategy ? "策略部位" : "單一合約"} · 定價波動率 ${pct(us.risk.sigma)}（${us.risk.sigma_source}）`);
    $("#us-risk-out").hidden = false;
    drawRisk();
  } catch (err) {
    setStatus($("#us-risk-status"), err.message, true);
  } finally {
    $("#us-risk-run").disabled = false;
  }
}
$("#us-risk-run").addEventListener("click", runRisk);

function drawRisk() {
  const r = us.risk;
  if (!r) return;
  const v = r.var;
  const varKpi = (label, s, note, main = false) =>
    kpi(label, s ? fmt(s.var, 2) : "—", s ? `ES ${fmt(s.expected_shortfall, 2)} · ${note}` : note, main);
  $("#us-var-kpis").innerHTML = [
    varKpi("歷史 VaR 95%", v.historical, "每股、1 日", true),
    varKpi("EWMA VaR 95%", v.ewma, "近期波動加權"),
    varKpi("IV 平滑 VaR 95%", v.iv, "以合約 IV 縮放"),
    kpi("標的價格", fmt(r.spot, 2)),
  ].join("");

  const m = r.matrix;
  plot($("#us-risk-chart"), [
    { type: "bar", x: m.map((x) => x.shock), y: m.map((x) => x.pnl), name: "損益", marker: { color: m.map((x) => (x.pnl >= 0 ? css("--up") : css("--down"))) }, hovertemplate: "衝擊 %{x:.1%}<br>損益 %{y:,.0f}<extra></extra>" },
    { x: m.map((x) => x.shock), y: m.map((x) => x.delta), name: "Delta", yaxis: "y2", mode: "lines+markers", line: { color: SERIES[0] } },
  ], {
    xaxis: { title: "標的價格衝擊", tickformat: ".0%", gridcolor: css("--border") },
    yaxis: { title: "損益", gridcolor: css("--border") },
    yaxis2: { title: "Delta", overlaying: "y", side: "right", showgrid: false },
    margin: { l: 64, r: 56, t: 8, b: 44 }, hovermode: "closest",
  });
  $("#us-risk-table").innerHTML = "<thead><tr><th>衝擊</th><th>標的價</th><th>損益</th><th>Delta</th><th>Gamma</th><th>Theta</th><th>Vega</th></tr></thead><tbody>" +
    m.map((x) => `<tr><td>${pct(x.shock)}</td><td>${fmt(x.underlying_price)}</td><td class="${signCls(x.pnl)}">${fmt(x.pnl, 0)}</td><td>${fmt(x.delta, 1)}</td><td>${fmt(x.gamma, 2)}</td><td>${fmt(x.theta, 1)}</td><td>${fmt(x.vega, 1)}</td></tr>`).join("") + "</tbody>";

  if (!r.curve) {
    $("#us-curve-kpis").innerHTML = "";
    $("#us-curve-hint").textContent = "價外 IV 節點不足，無法分析曲率";
    Plotly.purge($("#us-curve-chart"));
    return;
  }
  const cs = r.curve.summary, nodes = r.curve.nodes;
  $("#us-curve-kpis").innerHTML = [
    kpi("ATM IV", `${fmt(cs.atm_iv_pct, 1)}%`), kpi("IV 範圍", `${fmt(cs.iv_range_pct, 1)} 點`),
    kpi("最大 |曲率|", fmt(cs.max_abs_curvature, 4)), kpi("ATM 履約價", fmt(cs.atm_strike)),
  ].join("");
  const top = [...nodes].sort((a, b) => b.abs_curvature - a.abs_curvature).slice(0, 5);
  plot($("#us-curve-chart"), [
    { x: nodes.map((n) => n.strike), y: nodes.map((n) => n.iv_pct / 100), name: "IV", mode: "lines+markers", line: { color: SERIES[0], width: 2 }, marker: { size: 5 } },
    { x: nodes.map((n) => n.strike), y: nodes.map((n) => n.curvature), name: "曲率", yaxis: "y2", type: "bar", marker: { color: SERIES[3], opacity: 0.45 } },
    { x: top.map((n) => n.strike), y: top.map((n) => n.iv_pct / 100), name: "曲率最大 5 點", mode: "markers", marker: { color: SERIES[4], size: 11, symbol: "circle-open", line: { width: 2 } } },
  ], {
    xaxis: { title: "履約價", gridcolor: css("--border") },
    yaxis: { title: "IV", tickformat: ".0%", gridcolor: css("--border") },
    yaxis2: { title: "曲率", overlaying: "y", side: "right", showgrid: false },
    margin: { l: 56, r: 64, t: 8, b: 44 },
  });
}

usForm.addEventListener("submit", loadUS);
usForm.elements.expiration.addEventListener("change", loadUS);

// ---------------------------------------------------------------- Taiwan warrants
const twForm = $("#tw-upload");
const tw = { dataset: null, rows: [], selected: null, sort: { key: "iv", asc: true }, r: 0.015 };

const TW_COLUMNS = [
  { key: "warrant_id", label: "代碼", cls: "text" },
  { key: "name", label: "名稱", cls: "text" },
  { key: "issuer", label: "發行商", cls: "text" },
  { key: "kind", label: "類型", cls: "text", render: (v) => (v ? `<span class="tag ${v}">${v === "call" ? "認購" : "認售"}</span>` : "—") },
  { key: "close", label: "收盤", render: (v) => fmt(v, 2) },
  { key: "volume", label: "成交量", render: int },
  { key: "underlying_price", label: "標的價", render: (v) => fmt(v, 2) },
  { key: "strike", label: "履約價", render: (v) => fmt(v, 2) },
  { key: "ratio", label: "行使比例", render: (v) => fmt(v, 4) },
  { key: "days_to_expiry", label: "剩餘天數", render: int },
  { key: "iv", label: "自算 IV", render: (v) => pct(v) },
  { key: "tej_iv", label: "TEJ IV", render: (v) => pct(v) },
  { key: "tej_hist_vol", label: "歷史波動", render: (v) => pct(v) },
  { key: "iv_minus_hv", label: "IV − HV", render: (v) => `<span class="${signCls(-v)}">${pct(v)}</span>` },
  { key: "delta", label: "Δ / 張", render: (v) => fmt(v, 4) },
  { key: "effective_leverage", label: "有效槓桿", render: (v) => fmt(v, 1) },
  { key: "moneyness_label", label: "價內外", cls: "text", render: (v) => v ?? "—" },
];

async function uploadTW(e) {
  e.preventDefault();
  const f = new FormData(twForm);
  tw.r = parseFloat(f.get("r")) / 100;
  const body = new FormData();
  body.append("daily", f.get("daily"));
  if (f.get("terms") && f.get("terms").size) body.append("terms", f.get("terms"));
  const btn = $("button[type=submit]", twForm);
  btn.disabled = true;
  setStatus($("#tw-status"), "讀取中…");
  try {
    const s = await api("/api/warrants/upload", { method: "POST", body });
    tw.dataset = s;
    fillSelect($("#f-underlying"), s.underlyings);
    fillSelect($("#f-issuer"), s.issuers);
    $("#f-date").value = s.end || "";
    $("#f-date").min = s.start || "";
    $("#f-date").max = s.end || "";
    setStatus($("#tw-status"), s.has_terms ? "已載入（含條款）" : "已載入（無條款表：只顯示 TEJ IV）");
    $("#tw-empty").hidden = true;
    $("#tw-main").hidden = false;
    await loadSnapshot();
  } catch (err) {
    setStatus($("#tw-status"), err.message, true);
  } finally {
    btn.disabled = false;
  }
}

function fillSelect(sel, values) {
  sel.innerHTML = `<option value="">全部</option>` + values.map((v) => `<option>${v}</option>`).join("");
}

async function loadSnapshot() {
  const params = new URLSearchParams({ r: tw.r });
  if ($("#f-date").value) params.set("date", $("#f-date").value);
  const snap = await api(`/api/warrants/${tw.dataset.dataset_id}/snapshot?${params}`);
  tw.rows = snap.rows;
  drawTW();
  if (!tw.selected && tw.rows.length) selectWarrant(filteredRows()[0]?.warrant_id || tw.rows[0].warrant_id);
}

function filteredRows() {
  const u = $("#f-underlying").value, iss = $("#f-issuer").value, k = $("#f-kind").value;
  const minDays = parseFloat($("#f-days").value) || 0, tradedOnly = $("#f-traded").checked;
  return tw.rows.filter((r) =>
    (!u || r.underlying_id === u) && (!iss || r.issuer === iss) && (!k || r.kind === k) &&
    (r.days_to_expiry ?? 0) >= minDays && (!tradedOnly || r.traded));
}

function sortedRows(rows) {
  const { key, asc } = tw.sort;
  return [...rows].sort((a, b) => {
    const x = a[key], y = b[key];
    if (x === null || x === undefined) return 1;
    if (y === null || y === undefined) return -1;
    return (x > y ? 1 : x < y ? -1 : 0) * (asc ? 1 : -1);
  });
}

function drawTW() {
  if (!tw.dataset) return;
  const rows = filteredRows();
  const s = tw.dataset;
  const withIv = rows.filter((r) => r.iv !== null || r.tej_iv !== null);
  const median = (arr) => { const a = arr.filter((v) => v !== null).sort((x, y) => x - y); return a.length ? a[Math.floor(a.length / 2)] : null; };
  $("#tw-kpis").innerHTML = [
    kpi("權證數", int(s.warrants), `${s.underlyings.length} 個標的 · ${s.issuers.length} 家發行商`, true),
    kpi("資料期間", `${s.start ?? "—"}`, `至 ${s.end ?? "—"}`),
    kpi("篩選後", int(rows.length), `${withIv.length} 檔有 IV`),
    kpi("IV 中位數", pct(median(rows.map((r) => r.iv ?? r.tej_iv)))),
  ].join("");
  $("#tw-count").textContent = `${rows.length} 檔 · 點欄位標題排序`;

  const table = $("#tw-table");
  table.innerHTML =
    "<thead><tr>" + TW_COLUMNS.map((c) => `<th class="sortable ${c.cls || ""} ${tw.sort.key === c.key ? "sorted" + (tw.sort.asc ? " asc" : "") : ""}" data-key="${c.key}">${c.label}</th>`).join("") + "</tr></thead><tbody>" +
    sortedRows(rows).map((r) => `<tr data-id="${r.warrant_id}" class="${r.warrant_id === tw.selected ? "selected" : ""}">` +
      TW_COLUMNS.map((c) => `<td class="${c.cls || ""}">${c.render ? c.render(r[c.key]) : (r[c.key] ?? "—")}</td>`).join("") + "</tr>").join("") +
    "</tbody>";

  // IV distribution by issuer (our IV when available, else TEJ's).
  const groups = {};
  rows.forEach((r) => { const v = r.iv ?? r.tej_iv; if (v !== null && r.issuer) (groups[r.issuer] ||= []).push({ v, r }); });
  const issuers = Object.keys(groups).sort((a, b) => median(groups[a].map((x) => x.v)) - median(groups[b].map((x) => x.v)));
  plot($("#tw-issuer-chart"), issuers.map((iss, i) => ({
    type: "box", name: iss, y: groups[iss].map((x) => x.v), text: groups[iss].map((x) => `${x.r.warrant_id} ${x.r.name}`),
    boxpoints: "all", jitter: 0.4, pointpos: 0, marker: { size: 5, color: SERIES[i % SERIES.length] }, line: { color: SERIES[i % SERIES.length] },
    hovertemplate: "%{text}<br>IV %{y:.1%}<extra></extra>",
  })), { showlegend: false, hovermode: "closest", yaxis: { title: "隱含波動率", tickformat: ".0%", gridcolor: css("--border") } });
}

async function selectWarrant(id) {
  if (!id) return;
  tw.selected = id;
  $$("#tw-table tbody tr").forEach((tr) => tr.classList.toggle("selected", tr.dataset.id === id));
  try {
    const s = await api(`/api/warrants/${tw.dataset.dataset_id}/series?${new URLSearchParams({ warrant_id: id, r: tw.r })}`);
    tw.series = s;
    drawSeries();
  } catch (err) {
    $("#tw-series-title").textContent = err.message;
  }
}

function drawSeries() {
  const s = tw.series;
  if (!s) return;
  $("#tw-series-title").textContent = `${s.warrant_id} ${s.name ?? ""}`;
  const rows = s.rows, x = rows.map((r) => r.date);
  const traded = rows.filter((r) => r.traded);
  plot($("#tw-series-chart"), [
    { x: traded.map((r) => r.date), y: traded.map((r) => r.iv), name: "自算 IV（有成交日）", mode: "lines+markers", line: { color: SERIES[0], width: 2 }, marker: { size: 4 } },
    { x, y: rows.map((r) => r.tej_iv), name: "TEJ IV", mode: "lines", line: { color: SERIES[1], width: 1.5 } },
    { x, y: rows.map((r) => r.tej_hist_vol), name: "歷史波動", mode: "lines", line: { color: SERIES[5], width: 1.5, dash: "dot" } },
    { x, y: rows.map((r) => r.close), name: "權證收盤", yaxis: "y2", mode: "lines", line: { color: SERIES[2], width: 1.5 } },
  ], {
    yaxis: { title: "波動率", tickformat: ".0%", gridcolor: css("--border") },
    yaxis2: { title: "價格", overlaying: "y", side: "right", showgrid: false },
    margin: { l: 56, r: 56, t: 8, b: 44 },
  });
}

twForm.addEventListener("submit", uploadTW);
["#f-underlying", "#f-issuer", "#f-kind", "#f-days", "#f-traded"].forEach((id) => $(id).addEventListener("input", drawTW));
$("#f-date").addEventListener("change", () => loadSnapshot().catch((err) => setStatus($("#tw-status"), err.message, true)));
$("#tw-table").addEventListener("click", (e) => {
  const th = e.target.closest("th[data-key]");
  if (th) {
    const key = th.dataset.key;
    tw.sort = { key, asc: tw.sort.key === key ? !tw.sort.asc : true };
    drawTW();
    return;
  }
  const tr = e.target.closest("tbody tr");
  if (tr) selectWarrant(tr.dataset.id);
});

// ---------------------------------------------------------------- boot
function redrawAll() { drawCalc(); drawUS(); drawStrategy(); drawRisk(); drawTW(); drawSeries(); }
runCalc();
syncStrategyInputs();
