/**
 * MediCore — KPI (year filter) + General chat. Plotly loads before this file.
 */

(function () {
  "use strict";

  const BASE = "";
  const THEME_STORAGE_KEY = "mediCoreTheme";

  const PLOT_THEMES = {
    dark: {
      fontFamily: '"IBM Plex Sans", system-ui, sans-serif',
      paper: "transparent",
      plot: "rgba(22, 28, 40, 0.9)",
      grid: "rgba(148, 163, 184, 0.12)",
      tick: "#94a3b8",
      title: "#e2e8f0",
      linePrimary: "#60a5fa",
      lineMarker: "#93c5fd",
      barHue: [217, 200, 188, 172],
      pie: ["#60a5fa", "#a78bfa", "#34d399", "#fb7185", "#fbbf24", "#38bdf8"],
      emptyAnnotation: "#64748b",
      seriesColors: ["#60a5fa", "#34d399", "#a78bfa", "#fb923c"],
      singleLine: "#60a5fa",
    },
    light: {
      fontFamily: '"IBM Plex Sans", system-ui, sans-serif',
      paper: "transparent",
      plot: "rgba(248, 250, 252, 0.96)",
      grid: "rgba(71, 85, 105, 0.14)",
      tick: "#475569",
      title: "#1e293b",
      linePrimary: "#2563eb",
      lineMarker: "#3b82f6",
      barHue: [217, 199, 175, 158],
      pie: ["#2563eb", "#7c3aed", "#059669", "#e11d48", "#d97706", "#0284c7"],
      emptyAnnotation: "#64748b",
      seriesColors: ["#2563eb", "#0d9488", "#7c3aed", "#ea580c"],
      singleLine: "#2563eb",
    },
  };

  var baselineCache = null;
  var lastDynamicChart = null;

  function getPlotTheme() {
    var t = document.documentElement.dataset.theme === "light" ? "light" : "dark";
    return PLOT_THEMES[t];
  }

  function syncThemeToggleUI() {
    var btn = document.getElementById("themeToggle");
    var label = document.getElementById("themeToggleText");
    var icon = document.getElementById("themeToggleIcon");
    if (!btn || !label || !icon) return;
    var dark = document.documentElement.dataset.theme !== "light";
    btn.setAttribute("aria-pressed", dark ? "true" : "false");
    btn.setAttribute("aria-label", dark ? "Use light theme" : "Use dark theme");
    label.textContent = dark ? "Light" : "Dark";
    var sun =
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>';
    var moon =
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
    icon.innerHTML = dark ? sun : moon;
  }

  function applyTheme(theme) {
    var next = theme === "light" || theme === "dark" ? theme : null;
    if (!next) {
      next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    }
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch (_e) {}
    syncThemeToggleUI();

    if (typeof window.Plotly === "undefined") return;

    if (baselineCache) {
      renderBaselineCharts(baselineCache);
    }

    var wrap = document.getElementById("dynamicChartWrap");
    if (lastDynamicChart && wrap && !wrap.classList.contains("hidden")) {
      renderDynamicChart(lastDynamicChart);
    }

    requestAnimationFrame(function () {
      document.querySelectorAll("#baselineRoot .plot-host").forEach(function (el) {
        try {
          window.Plotly.Plots.resize(el);
        } catch (_e) {}
      });
      var dp = document.getElementById("dynamicPlot");
      if (dp && wrap && !wrap.classList.contains("hidden")) {
        try {
          window.Plotly.Plots.resize(dp);
        } catch (_e2) {}
      }
    });
  }

  function yearBounds(y) {
    var year = String(y);
    return { start: year + "-01-01", end: year + "-12-31" };
  }

  function plotlyLayoutBase(titleText, opts) {
    var P = getPlotTheme();
    var h = opts && opts.height ? opts.height : 320;
    return {
      title: { text: titleText, font: { size: 14, color: P.title, family: P.fontFamily } },
      paper_bgcolor: P.paper,
      plot_bgcolor: P.plot,
      font: { color: P.tick, family: P.fontFamily, size: 11 },
      height: h,
      margin: { t: 44, r: 12, b: 56, l: 52 },
      xaxis: {
        gridcolor: P.grid,
        zeroline: false,
        tickfont: { color: P.tick, size: 10 },
        title: { font: { size: 11, color: P.tick } },
      },
      yaxis: {
        gridcolor: P.grid,
        zeroline: false,
        tickfont: { color: P.tick, size: 10 },
        title: { font: { size: 11, color: P.tick } },
      },
    };
  }

  function emptyFigure(title, message) {
    var P = getPlotTheme();
    var L = plotlyLayoutBase(title);
    return {
      data: [
        {
          type: "scatter",
          x: [0],
          y: [0],
          mode: "markers",
          marker: { size: 0, opacity: 0 },
          hoverinfo: "skip",
          showlegend: false,
        },
      ],
      layout: {
        ...L,
        annotations: [
          {
            text: message,
            xref: "paper",
            yref: "paper",
            x: 0.5,
            y: 0.5,
            showarrow: false,
            font: { size: 13, color: P.emptyAnnotation, family: P.fontFamily },
          },
        ],
        xaxis: { ...L.xaxis, visible: false },
        yaxis: { ...L.yaxis, visible: false },
      },
    };
  }

  function baselineFigure(spec, rows) {
    var P = getPlotTheme();
    var cat = spec.category_key || (rows[0] ? Object.keys(rows[0])[0] : "x");
    var val = spec.value_key || (rows[0] ? Object.keys(rows[0])[1] : "y");
    var L = plotlyLayoutBase(spec.title);
    L.xaxis = { ...L.xaxis, title: { ...L.xaxis.title, text: spec.x_label || cat } };
    L.yaxis = { ...L.yaxis, title: { ...L.yaxis.title, text: spec.y_label || val } };

    if (!rows || !rows.length) {
      return emptyFigure(spec.title, "No data for this year.");
    }

    var x = rows.map(function (r) {
      return r[cat];
    });
    var y = rows.map(function (r) {
      return r[val];
    });

    if (spec.kind === "line") {
      return {
        data: [
          {
            x: x,
            y: y,
            type: "scatter",
            mode: "lines+markers",
            line: { color: P.linePrimary, width: 2 },
            marker: { size: 7, color: P.lineMarker },
          },
        ],
        layout: L,
      };
    }
    if (spec.kind === "bar") {
      return {
        data: [
          {
            x: x,
            y: y,
            type: "bar",
            marker: {
              color: y.map(function (_, i) {
                var h = P.barHue[i % P.barHue.length];
                return "hsla(" + h + ", 58%, 58%, 0.92)";
              }),
            },
          },
        ],
        layout: { ...L, xaxis: { ...L.xaxis, tickangle: -32 } },
      };
    }
    if (spec.kind === "pie") {
      return {
        data: [
          {
            type: "pie",
            labels: x,
            values: y,
            hole: 0.5,
            textinfo: "label+percent",
            textfont: { size: 11, color: P.title },
            marker: { colors: P.pie },
          },
        ],
        layout: {
          ...plotlyLayoutBase(spec.title),
          showlegend: true,
          legend: {
            orientation: "h",
            y: -0.12,
            font: { color: P.tick, size: 10, family: P.fontFamily },
          },
        },
      };
    }
    return emptyFigure(spec.title, "Unknown chart type.");
  }

  function setBaselineStatus(msg, kind) {
    var el = document.getElementById("baselineStatus");
    if (!msg) {
      el.classList.add("hidden");
      el.textContent = "";
      return;
    }
    el.textContent = msg;
    el.className = "banner " + (kind === "error" ? "banner-error" : "banner-info");
    el.classList.remove("hidden");
  }

  function populateYearSelect() {
    var sel = document.getElementById("kpiYear");
    if (!sel) return;
    var y = new Date().getFullYear();
    sel.innerHTML = "";
    for (var i = 0; i <= 12; i++) {
      var year = y - i;
      var opt = document.createElement("option");
      opt.value = String(year);
      opt.textContent = String(year);
      if (i === 0) opt.selected = true;
      sel.appendChild(opt);
    }
  }

  function renderBaselineCharts(data) {
    var root = document.getElementById("baselineRoot");
    if (!root || typeof window.Plotly === "undefined") return false;

    var specs = data.chart_specs || [];
    if (!specs.length) return false;

    root.innerHTML = "";
    for (var i = 0; i < specs.length; i++) {
      var spec = specs[i];
      var rows = (data.panels && data.panels[spec.chart_id]) || [];
      var card = document.createElement("article");
      card.className = "chart-tile";
      var h = document.createElement("h3");
      h.textContent = spec.title;
      var plotDiv = document.createElement("div");
      plotDiv.className = "plot-host";
      plotDiv.id = "base-" + spec.chart_id;
      card.appendChild(h);
      card.appendChild(plotDiv);
      root.appendChild(card);

      var fig = baselineFigure(spec, rows);
      window.Plotly.newPlot(plotDiv.id, fig.data, fig.layout, {
        responsive: true,
        displayModeBar: "hover",
        displaylogo: false,
      });
    }
    return true;
  }

  async function loadBaseline() {
    var root = document.getElementById("baselineRoot");
    var yearEl = document.getElementById("kpiYear");
    var year = yearEl ? yearEl.value : String(new Date().getFullYear());
    var bounds = yearBounds(year);
    var pill = document.getElementById("rangePill");
    if (pill) pill.textContent = "Year " + year;

    if (typeof window.Plotly === "undefined") {
      setBaselineStatus("Chart library failed to load. Check network or cdn.plot.ly.", "error");
      root.innerHTML = "";
      baselineCache = null;
      return;
    }

    root.innerHTML = "";
    setBaselineStatus("Loading…", "info");

    var data;
    try {
      var q =
        "start=" +
        encodeURIComponent(bounds.start) +
        "&end=" +
        encodeURIComponent(bounds.end);
      var res = await fetch(BASE + "/api/dashboard/baseline?" + q);
      var text = await res.text();
      if (!res.ok) {
        throw new Error(text || res.statusText);
      }
      data = JSON.parse(text);
    } catch (e) {
      baselineCache = null;
      setBaselineStatus("Could not load KPIs: " + (e.message || String(e)), "error");
      root.innerHTML =
        '<p class="chat-status">Ensure <code>SUPABASE_DB_URL</code> is set and the server is running.</p>';
      return;
    }

    var specs = data.chart_specs || [];
    if (!specs.length) {
      baselineCache = null;
      setBaselineStatus("No chart definitions returned from API.", "error");
      return;
    }

    renderBaselineCharts(data);
    baselineCache = data;
    setBaselineStatus("", "info");
  }

  function renderDynamicChart(chart) {
    var wrap = document.getElementById("dynamicChartWrap");
    var plotEl = document.getElementById("dynamicPlot");
    if (!chart || typeof window.Plotly === "undefined") {
      wrap.classList.add("hidden");
      lastDynamicChart = null;
      return;
    }
    var P = getPlotTheme();
    wrap.classList.remove("hidden");
    plotEl.innerHTML = "";
    var xk = chart.x_key;
    var rows = chart.rows || [];
    var t = plotlyLayoutBase(chart.title || "Result", { height: 360 });
    t.legend = {
      orientation: "h",
      y: -0.18,
      font: { color: P.tick, family: P.fontFamily },
    };
    t.xaxis = { ...t.xaxis, title: { ...t.xaxis.title, text: xk } };
    t.yaxis = { ...t.yaxis, title: { ...t.yaxis.title, text: "Value" } };

    var traces = [];
    var colors = P.seriesColors;
    if (chart.series && chart.series.length) {
      chart.series.forEach(function (s, i) {
        var xv = rows.map(function (r) {
          return r[xk];
        });
        var yv = rows.map(function (r) {
          return r[s.key];
        });
        var name = s.label || s.key;
        var c = colors[i % colors.length];
        if (chart.kind === "bar") {
          traces.push({ x: xv, y: yv, name: name, type: "bar", marker: { color: c } });
        } else {
          traces.push({
            x: xv,
            y: yv,
            name: name,
            type: "scatter",
            mode: "lines+markers",
            line: { color: c },
          });
        }
      });
    } else if (chart.y_key) {
      var bar = chart.kind === "bar";
      var xv = rows.map(function (r) {
        return r[xk];
      });
      var yv = rows.map(function (r) {
        return r[chart.y_key];
      });
      traces = bar
        ? [{ x: xv, y: yv, type: "bar", marker: { color: P.singleLine } }]
        : [
            {
              x: xv,
              y: yv,
              type: "scatter",
              mode: "lines+markers",
              line: { color: P.singleLine },
            },
          ];
    } else {
      wrap.classList.add("hidden");
      lastDynamicChart = null;
      return;
    }

    lastDynamicChart = chart;
    window.Plotly.newPlot("dynamicPlot", traces, t, { responsive: true, displaylogo: false });
  }

  function appendMessage(role, text) {
    var thread = document.getElementById("chatThread");
    var wrap = document.createElement("div");
    wrap.className = "msg " + (role === "user" ? "msg-user" : "msg-assistant");
    var meta = document.createElement("div");
    meta.className = "msg-meta";
    meta.textContent = role === "user" ? "You" : "Assistant";
    var body = document.createElement("div");
    body.className = "msg-body";
    body.textContent = text;
    wrap.appendChild(meta);
    wrap.appendChild(body);
    thread.appendChild(wrap);
    thread.scrollTop = thread.scrollHeight;
  }

  function setView(name) {
    var kpi = document.getElementById("viewKpi");
    var chat = document.getElementById("viewChat");
    var navKpi = document.getElementById("navKpi");
    var navChat = document.getElementById("navChat");

    if (name === "kpi") {
      kpi.classList.add("is-visible");
      chat.classList.remove("is-visible");
      navKpi.classList.add("is-active");
      navChat.classList.remove("is-active");
      navKpi.setAttribute("aria-current", "page");
      navChat.removeAttribute("aria-current");
      if (typeof window.Plotly !== "undefined") {
        document.querySelectorAll("#baselineRoot .plot-host").forEach(function (el) {
          try {
            window.Plotly.Plots.resize(el);
          } catch (_e) {}
        });
      }
    } else {
      kpi.classList.remove("is-visible");
      chat.classList.add("is-visible");
      navKpi.classList.remove("is-active");
      navChat.classList.add("is-active");
      navChat.setAttribute("aria-current", "page");
      navKpi.removeAttribute("aria-current");
      var wrap = document.getElementById("dynamicChartWrap");
      var dp = document.getElementById("dynamicPlot");
      if (
        wrap &&
        !wrap.classList.contains("hidden") &&
        dp &&
        typeof window.Plotly !== "undefined"
      ) {
        try {
          window.Plotly.Plots.resize(dp);
        } catch (_e) {}
      }
    }
  }

  var chatMemory = [];

  async function sendChat() {
    var input = document.getElementById("chatInput");
    var msg = input.value.trim();
    var status = document.getElementById("chatStatus");
    var btn = document.getElementById("sendChat");
    var dynWrap = document.getElementById("dynamicChartWrap");

    if (!msg) {
      status.textContent = "Type a message to send.";
      return;
    }
    btn.disabled = true;
    status.textContent = "Sending…";
    dynWrap.classList.add("hidden");
    lastDynamicChart = null;

    appendMessage("user", msg);
    input.value = "";

    try {
      var res = await fetch(BASE + "/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, memory: chatMemory }),
      });
      var raw = await res.text();
      var out;
      try {
        out = JSON.parse(raw);
      } catch {
        throw new Error(raw.slice(0, 200));
      }
      if (!res.ok) {
        throw new Error(out.detail || raw);
      }

      if (Array.isArray(out.memory)) {
        chatMemory = out.memory;
      }

      var text = out.insight || out.message || "";
      appendMessage("assistant", text || "(No text reply.)");

      if (out.chart) {
        renderDynamicChart(out.chart);
        status.textContent = "Reply received with a chart.";
      } else {
        status.textContent = "Reply received.";
      }
    } catch (e) {
      status.textContent = "Error: " + (e.message || String(e));
      appendMessage("assistant", "Something went wrong: " + (e.message || String(e)));
    } finally {
      btn.disabled = false;
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    syncThemeToggleUI();

    var themeBtn = document.getElementById("themeToggle");
    if (themeBtn) {
      themeBtn.addEventListener("click", function () {
        applyTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light");
      });
    }

    populateYearSelect();

    document.getElementById("navKpi").addEventListener("click", function () {
      setView("kpi");
    });
    document.getElementById("navChat").addEventListener("click", function () {
      setView("chat");
    });

    document.getElementById("reloadKpi").addEventListener("click", function () {
      loadBaseline();
    });
    document.getElementById("kpiYear").addEventListener("change", function () {
      loadBaseline();
    });

    document.getElementById("sendChat").addEventListener("click", sendChat);
    document.getElementById("chatInput").addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" && !ev.shiftKey) {
        ev.preventDefault();
        sendChat();
      }
    });

    loadBaseline();
  });
})();
