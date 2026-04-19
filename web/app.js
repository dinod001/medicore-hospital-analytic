/**
 * MediCore — KPI (year filter) + General chat. Plotly loads before this file.
 */

(function () {
  "use strict";

  const BASE = "";

  const PLOT = {
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
  };

  function yearBounds(y) {
    const year = String(y);
    return { start: year + "-01-01", end: year + "-12-31" };
  }

  function plotlyLayoutBase(titleText, opts) {
    const h = opts && opts.height ? opts.height : 320;
    return {
      title: { text: titleText, font: { size: 14, color: PLOT.title, family: PLOT.fontFamily } },
      paper_bgcolor: PLOT.paper,
      plot_bgcolor: PLOT.plot,
      font: { color: PLOT.tick, family: PLOT.fontFamily, size: 11 },
      height: h,
      margin: { t: 44, r: 12, b: 56, l: 52 },
      xaxis: {
        gridcolor: PLOT.grid,
        zeroline: false,
        tickfont: { color: PLOT.tick, size: 10 },
        title: { font: { size: 11, color: PLOT.tick } },
      },
      yaxis: {
        gridcolor: PLOT.grid,
        zeroline: false,
        tickfont: { color: PLOT.tick, size: 10 },
        title: { font: { size: 11, color: PLOT.tick } },
      },
    };
  }

  function emptyFigure(title, message) {
    const L = plotlyLayoutBase(title);
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
            font: { size: 13, color: "#64748b", family: PLOT.fontFamily },
          },
        ],
        xaxis: { ...L.xaxis, visible: false },
        yaxis: { ...L.yaxis, visible: false },
      },
    };
  }

  function baselineFigure(spec, rows) {
    const cat = spec.category_key || (rows[0] ? Object.keys(rows[0])[0] : "x");
    const val = spec.value_key || (rows[0] ? Object.keys(rows[0])[1] : "y");
    const L = plotlyLayoutBase(spec.title);
    L.xaxis = { ...L.xaxis, title: { ...L.xaxis.title, text: spec.x_label || cat } };
    L.yaxis = { ...L.yaxis, title: { ...L.yaxis.title, text: spec.y_label || val } };

    if (!rows || !rows.length) {
      return emptyFigure(spec.title, "No data for this year.");
    }

    const x = rows.map(function (r) {
      return r[cat];
    });
    const y = rows.map(function (r) {
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
            line: { color: PLOT.linePrimary, width: 2 },
            marker: { size: 7, color: PLOT.lineMarker },
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
                const h = PLOT.barHue[i % PLOT.barHue.length];
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
            textfont: { size: 11, color: PLOT.title },
            marker: { colors: PLOT.pie },
          },
        ],
        layout: {
          ...plotlyLayoutBase(spec.title),
          showlegend: true,
          legend: {
            orientation: "h",
            y: -0.12,
            font: { color: PLOT.tick, size: 10, family: PLOT.fontFamily },
          },
        },
      };
    }
    return emptyFigure(spec.title, "Unknown chart type.");
  }

  function setBaselineStatus(msg, kind) {
    const el = document.getElementById("baselineStatus");
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
    const sel = document.getElementById("kpiYear");
    if (!sel) return;
    const y = new Date().getFullYear();
    sel.innerHTML = "";
    for (let i = 0; i <= 12; i++) {
      const year = y - i;
      const opt = document.createElement("option");
      opt.value = String(year);
      opt.textContent = String(year);
      if (i === 0) opt.selected = true;
      sel.appendChild(opt);
    }
  }

  async function loadBaseline() {
    const root = document.getElementById("baselineRoot");
    const yearEl = document.getElementById("kpiYear");
    const year = yearEl ? yearEl.value : String(new Date().getFullYear());
    const bounds = yearBounds(year);
    const pill = document.getElementById("rangePill");
    if (pill) pill.textContent = "Year " + year;

    if (typeof window.Plotly === "undefined") {
      setBaselineStatus("Chart library failed to load. Check network or cdn.plot.ly.", "error");
      root.innerHTML = "";
      return;
    }

    root.innerHTML = "";
    setBaselineStatus("Loading…", "info");

    let data;
    try {
      const q =
        "start=" +
        encodeURIComponent(bounds.start) +
        "&end=" +
        encodeURIComponent(bounds.end);
      const res = await fetch(BASE + "/api/dashboard/baseline?" + q);
      const text = await res.text();
      if (!res.ok) {
        throw new Error(text || res.statusText);
      }
      data = JSON.parse(text);
    } catch (e) {
      setBaselineStatus("Could not load KPIs: " + (e.message || String(e)), "error");
      root.innerHTML =
        '<p class="chat-status">Ensure <code>SUPABASE_DB_URL</code> is set and the server is running.</p>';
      return;
    }

    const specs = data.chart_specs || [];
    if (!specs.length) {
      setBaselineStatus("No chart definitions returned from API.", "error");
      return;
    }

    for (let i = 0; i < specs.length; i++) {
      const spec = specs[i];
      const rows = (data.panels && data.panels[spec.chart_id]) || [];
      const card = document.createElement("article");
      card.className = "chart-tile";
      const h = document.createElement("h3");
      h.textContent = spec.title;
      const plotDiv = document.createElement("div");
      plotDiv.className = "plot-host";
      plotDiv.id = "base-" + spec.chart_id;
      card.appendChild(h);
      card.appendChild(plotDiv);
      root.appendChild(card);

      const fig = baselineFigure(spec, rows);
      window.Plotly.newPlot(plotDiv.id, fig.data, fig.layout, {
        responsive: true,
        displayModeBar: "hover",
        displaylogo: false,
      });
    }

    setBaselineStatus("", "info");
  }

  function renderDynamicChart(chart) {
    const wrap = document.getElementById("dynamicChartWrap");
    const plotEl = document.getElementById("dynamicPlot");
    if (!chart || typeof window.Plotly === "undefined") {
      wrap.classList.add("hidden");
      return;
    }
    wrap.classList.remove("hidden");
    plotEl.innerHTML = "";
    const xk = chart.x_key;
    const rows = chart.rows || [];
    const t = plotlyLayoutBase(chart.title || "Result", { height: 360 });
    t.legend = {
      orientation: "h",
      y: -0.18,
      font: { color: PLOT.tick, family: PLOT.fontFamily },
    };
    t.xaxis = { ...t.xaxis, title: { ...t.xaxis.title, text: xk } };
    t.yaxis = { ...t.yaxis, title: { ...t.yaxis.title, text: "Value" } };

    let traces = [];
    const colors = ["#60a5fa", "#34d399", "#a78bfa", "#fb923c"];
    if (chart.series && chart.series.length) {
      chart.series.forEach(function (s, i) {
        const xv = rows.map(function (r) {
          return r[xk];
        });
        const yv = rows.map(function (r) {
          return r[s.key];
        });
        const name = s.label || s.key;
        const c = colors[i % colors.length];
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
      const bar = chart.kind === "bar";
      const xv = rows.map(function (r) {
        return r[xk];
      });
      const yv = rows.map(function (r) {
        return r[chart.y_key];
      });
      traces = bar
        ? [{ x: xv, y: yv, type: "bar", marker: { color: "#60a5fa" } }]
        : [
            {
              x: xv,
              y: yv,
              type: "scatter",
              mode: "lines+markers",
              line: { color: "#60a5fa" },
            },
          ];
    } else {
      wrap.classList.add("hidden");
      return;
    }

    window.Plotly.newPlot("dynamicPlot", traces, t, { responsive: true, displaylogo: false });
  }

  function appendMessage(role, text) {
    const thread = document.getElementById("chatThread");
    const wrap = document.createElement("div");
    wrap.className = "msg " + (role === "user" ? "msg-user" : "msg-assistant");
    const meta = document.createElement("div");
    meta.className = "msg-meta";
    meta.textContent = role === "user" ? "You" : "Assistant";
    const body = document.createElement("div");
    body.className = "msg-body";
    body.textContent = text;
    wrap.appendChild(meta);
    wrap.appendChild(body);
    thread.appendChild(wrap);
    thread.scrollTop = thread.scrollHeight;
  }

  function setView(name) {
    const kpi = document.getElementById("viewKpi");
    const chat = document.getElementById("viewChat");
    const navKpi = document.getElementById("navKpi");
    const navChat = document.getElementById("navChat");

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
      const wrap = document.getElementById("dynamicChartWrap");
      const dp = document.getElementById("dynamicPlot");
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

  let chatMemory = [];

  async function sendChat() {
    const input = document.getElementById("chatInput");
    const msg = input.value.trim();
    const status = document.getElementById("chatStatus");
    const btn = document.getElementById("sendChat");
    const dynWrap = document.getElementById("dynamicChartWrap");

    if (!msg) {
      status.textContent = "Type a message to send.";
      return;
    }
    btn.disabled = true;
    status.textContent = "Sending…";
    dynWrap.classList.add("hidden");

    appendMessage("user", msg);
    input.value = "";

    try {
      const res = await fetch(BASE + "/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, memory: chatMemory }),
      });
      const raw = await res.text();
      let out;
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

      const text = out.insight || out.message || "";
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
