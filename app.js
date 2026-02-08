const WORK_CATEGORIES = [
  "Tracking / ETA",
  "Exception / Delay",
  "Documentation",
  "Rate / Pricing",
  "Internal Coordination",
  "Other",
];

const HANDLING_MINUTES = {
  "Tracking / ETA": 4,
  "Exception / Delay": 12,
  Documentation: 7,
  "Rate / Pricing": 8,
  "Internal Coordination": 6,
  Other: 5,
};

const CATEGORY_KEYWORDS = {
  "Exception / Delay": [
    "delay", "late", "missed", "issue", "problem", "stuck", "hold", "damaged",
    "shortage", "escalat", "failed delivery", "cancelled", "detention", "demurrage",
  ],
  "Tracking / ETA": [
    "eta", "track", "tracking", "status update", "where is", "arrival time",
    "delivery time", "in transit",
  ],
  Documentation: [
    "invoice", "pod", "bill of lading", "bol", "awb", "packing list", "customs",
    "document", "paperwork", "declaration", "certificate", "forms",
  ],
  "Rate / Pricing": [
    "rate", "pricing", "quote", "quotation", "cost", "charge", "tariff", "spot rate",
  ],
  "Internal Coordination": [
    "please coordinate", "warehouse", "dispatch", "driver", "pickup schedule", "handover",
    "internal", "team", "ops", "arrange pickup",
  ],
};

const EXCEPTION_KEYWORDS = [
  "urgent", "escalat", "problem", "failed", "delay", "late", "stuck", "damage", "asap", "critical",
];

const SLA_KEYWORDS = [
  "urgent", "asap", "today", "immediately", "deadline", "cutoff", "cut-off", "demurrage",
  "detention", "customer waiting", "sla", "missed",
];

const state = {
  report: null,
};

const el = {
  inputMode: document.getElementById("inputMode"),
  lookbackDays: document.getElementById("lookbackDays"),
  maxItems: document.getElementById("maxItems"),
  fileInput: document.getElementById("fileInput"),
  fileMeta: document.getElementById("fileMeta"),
  textInput: document.getElementById("textInput"),
  generateBtn: document.getElementById("generateBtn"),
  sampleBtn: document.getElementById("sampleBtn"),
  pdfBtn: document.getElementById("pdfBtn"),
  status: document.getElementById("status"),
  reportPanel: document.getElementById("reportPanel"),
  reportRoot: document.getElementById("reportRoot"),
};

function setStatus(message, isError = false) {
  el.status.textContent = message;
  el.status.classList.toggle("error", isError);
}

function humanFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let idx = 0;
  while (value >= 1024 && idx < units.length - 1) {
    value /= 1024;
    idx += 1;
  }
  const rounded = idx === 0 ? value.toFixed(0) : value.toFixed(1);
  return `${rounded} ${units[idx]}`;
}

function updateFileMeta() {
  const file = el.fileInput.files[0];
  if (!file) {
    el.fileMeta.textContent = "No file selected.";
    return;
  }
  el.fileMeta.textContent = `Selected: ${file.name} (${humanFileSize(file.size)})`;
}

function parseTimestamp(value) {
  if (!value || !String(value).trim()) {
    return null;
  }
  const raw = String(value).trim();
  const candidates = [raw, raw.replace(" ", "T"), raw.endsWith("Z") ? raw : `${raw}Z`];

  for (const candidate of candidates) {
    const dt = new Date(candidate);
    if (!Number.isNaN(dt.getTime())) {
      return dt;
    }
  }
  return null;
}

function parseCsvRows(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    const next = text[i + 1];

    if (ch === '"') {
      if (inQuotes && next === '"') {
        field += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (ch === "," && !inQuotes) {
      row.push(field);
      field = "";
      continue;
    }

    if ((ch === "\n" || ch === "\r") && !inQuotes) {
      if (ch === "\r" && next === "\n") {
        i += 1;
      }
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
      continue;
    }

    field += ch;
  }

  if (field.length > 0 || row.length > 0) {
    row.push(field);
    rows.push(row);
  }

  return rows.filter((r) => r.some((cell) => String(cell).trim() !== ""));
}

function normalizeCsvItems(text) {
  const rows = parseCsvRows(text);
  if (rows.length < 2) {
    return [];
  }
  const headers = rows[0].map((h) => String(h || "").trim().toLowerCase());
  const idx = {
    timestamp: headers.indexOf("timestamp"),
    sender: headers.indexOf("sender"),
    subject: headers.indexOf("subject"),
    body: headers.indexOf("body"),
  };

  return rows
    .slice(1)
    .map((row, i) => {
      const subject = idx.subject >= 0 ? String(row[idx.subject] || "").trim() : "";
      const body = idx.body >= 0 ? String(row[idx.body] || "").trim() : "";
      return {
        id: `csv-${i + 1}`,
        timestamp: idx.timestamp >= 0 ? parseTimestamp(row[idx.timestamp]) : null,
        sender: idx.sender >= 0 ? String(row[idx.sender] || "").trim() : "",
        subject,
        body,
        source: "csv",
      };
    })
    .filter((item) => item.subject || item.body);
}

function normalizeTextBatchItems(text) {
  const blocks = text.split(/^\s*---\s*$/m).map((x) => x.trim()).filter(Boolean);
  return blocks
    .map((block, i) => {
      const lines = block.split(/\r?\n/);
      const readHeader = (name) => {
        const line = lines.find((entry) => entry.toLowerCase().startsWith(`${name}:`));
        return line ? line.split(":").slice(1).join(":").trim() : "";
      };

      const timestamp = parseTimestamp(readHeader("timestamp"));
      const sender = readHeader("sender");
      let subject = readHeader("subject");

      const bodyMarker = block.match(/^body\s*:\s*$/im);
      let body = "";
      if (bodyMarker) {
        const split = block.split(/^body\s*:\s*$/im);
        body = split.slice(1).join("\n").trim();
      } else {
        body = block;
      }

      if (!subject) {
        const firstLine = (body.split(/\r?\n/).find(Boolean) || "").trim();
        subject = firstLine.length > 80 ? `${firstLine.slice(0, 80)}...` : firstLine;
      }

      return {
        id: `text-${i + 1}`,
        timestamp,
        sender,
        subject,
        body,
        source: "text",
      };
    })
    .filter((item) => item.subject || item.body);
}

function containsAny(text, phrases) {
  return phrases.some((p) => text.includes(p));
}

function classifyItem(item) {
  const text = `${item.subject}\n${item.body}`.toLowerCase();
  const scores = {};

  Object.keys(CATEGORY_KEYWORDS).forEach((category) => {
    let score = 0;
    CATEGORY_KEYWORDS[category].forEach((kw) => {
      if (text.includes(kw)) {
        score += 1;
      }
    });
    scores[category] = score;
  });

  let category = "Other";
  let topScore = 0;
  WORK_CATEGORIES.forEach((cat) => {
    const score = scores[cat] || 0;
    if (score > topScore) {
      topScore = score;
      category = cat;
    }
  });

  const isException = category === "Exception / Delay" || containsAny(text, EXCEPTION_KEYWORDS);
  const nature = isException ? "Exception-driven" : "Repetitive";

  const isSla = containsAny(text, SLA_KEYWORDS) || (category === "Exception / Delay" && text.includes("urgent"));
  const risk = isSla ? "SLA-sensitive" : "Not SLA-sensitive";

  let confidence = 0.5;
  if (category !== "Other") {
    confidence = Math.min(0.95, 0.55 + topScore * 0.1);
  }

  return {
    category,
    nature,
    risk,
    confidence: Math.round(confidence * 100) / 100,
  };
}

function percent(count, total) {
  if (!total) {
    return 0;
  }
  return Math.round((count / total) * 1000) / 10;
}

function limitItems(items, lookbackDays, maxItems) {
  const now = new Date();
  const timestamps = items
    .map((item) => item.timestamp)
    .filter((value) => value instanceof Date && !Number.isNaN(value.getTime()));

  const anchorDate = timestamps.length
    ? new Date(Math.max(...timestamps.map((value) => value.getTime())))
    : now;

  const threshold = new Date(anchorDate);
  threshold.setDate(threshold.getDate() - lookbackDays);

  const sorted = [...items].sort((a, b) => {
    const aTime = a.timestamp instanceof Date ? a.timestamp.getTime() : anchorDate.getTime();
    const bTime = b.timestamp instanceof Date ? b.timestamp.getTime() : anchorDate.getTime();
    return bTime - aTime;
  });

  const withinWindow = sorted.filter((item) => {
    if (!(item.timestamp instanceof Date)) {
      return true;
    }
    return item.timestamp >= threshold;
  });

  if (withinWindow.length > 0) {
    return {
      items: withinWindow.slice(0, maxItems),
      appliedLookback: true,
      anchorDate,
      fallbackUsed: false,
    };
  }

  return {
    items: sorted.slice(0, maxItems),
    appliedLookback: false,
    anchorDate,
    fallbackUsed: true,
  };
}

function aggregate(classifiedItems, lookbackDays) {
  const total = classifiedItems.length;
  if (!total) {
    return {
      totalVolume: 0,
      periodDays: lookbackDays,
      categoryCounts: {},
      categoryPercentages: {},
      natureCounts: {},
      naturePercentages: {},
      riskCounts: {},
      riskPercentages: {},
      estimatedMinutesByCategory: {},
      estimatedTotalMinutes: 0,
      estimatedHoursPerWeek: 0,
      slaClusters: [],
    };
  }

  const timestamps = classifiedItems.map((x) => x.item.timestamp).filter((x) => x instanceof Date);

  let periodDays = lookbackDays;
  if (timestamps.length) {
    const minTime = Math.min(...timestamps.map((d) => d.getTime()));
    const maxTime = Math.max(...timestamps.map((d) => d.getTime()));
    periodDays = Math.max(1, Math.floor((maxTime - minTime) / (1000 * 60 * 60 * 24)) + 1);
  }

  const countBy = (selector) => {
    const counts = {};
    classifiedItems.forEach((x) => {
      const key = selector(x);
      counts[key] = (counts[key] || 0) + 1;
    });
    return counts;
  };

  const categoryCounts = countBy((x) => x.classification.category);
  const natureCounts = countBy((x) => x.classification.nature);
  const riskCounts = countBy((x) => x.classification.risk);

  const categoryPercentages = {};
  Object.entries(categoryCounts).forEach(([k, v]) => {
    categoryPercentages[k] = percent(v, total);
  });

  const naturePercentages = {};
  Object.entries(natureCounts).forEach(([k, v]) => {
    naturePercentages[k] = percent(v, total);
  });

  const riskPercentages = {};
  Object.entries(riskCounts).forEach(([k, v]) => {
    riskPercentages[k] = percent(v, total);
  });

  const estimatedMinutesByCategory = {};
  Object.entries(categoryCounts).forEach(([k, v]) => {
    estimatedMinutesByCategory[k] = v * (HANDLING_MINUTES[k] || HANDLING_MINUTES.Other);
  });

  const estimatedTotalMinutes = Object.values(estimatedMinutesByCategory).reduce((sum, n) => sum + n, 0);
  const estimatedHoursPerWeek = Math.round((estimatedTotalMinutes / 60) * (7 / periodDays) * 10) / 10;

  const slaCountsByCategory = {};
  classifiedItems.forEach((x) => {
    if (x.classification.risk === "SLA-sensitive") {
      const key = x.classification.category;
      slaCountsByCategory[key] = (slaCountsByCategory[key] || 0) + 1;
    }
  });

  const totalSla = Object.values(slaCountsByCategory).reduce((sum, n) => sum + n, 0);
  const slaClusters = Object.entries(slaCountsByCategory)
    .map(([category, count]) => ({ category, count, shareOfSla: percent(count, totalSla) }))
    .sort((a, b) => b.count - a.count);

  return {
    totalVolume: total,
    periodDays,
    categoryCounts,
    categoryPercentages,
    natureCounts,
    naturePercentages,
    riskCounts,
    riskPercentages,
    estimatedMinutesByCategory,
    estimatedTotalMinutes,
    estimatedHoursPerWeek,
    slaClusters,
  };
}

function leverageSummary(metrics) {
  if (!metrics.totalVolume) {
    return ["No inbound items in selected window; no leverage estimate available."];
  }

  const repetitivePct = metrics.naturePercentages.Repetitive || 0;
  const slaPct = metrics.riskPercentages["SLA-sensitive"] || 0;
  const topCats = Object.entries(metrics.categoryCounts).sort((a, b) => b[1] - a[1]).slice(0, 2);

  const lines = [];
  if (repetitivePct >= 50) {
    lines.push(`${repetitivePct}% of inbound work appears repetitive and is a candidate for templated AI handling.`);
  } else {
    lines.push(`Repetitive work is ${repetitivePct}%; prioritize exception triage before broad automation.`);
  }

  if (topCats.length) {
    lines.push(`Highest-load categories: ${topCats.map(([name, count]) => `${name} (${count})`).join(", ")}.`);
  }

  if (slaPct > 0) {
    lines.push(`SLA-sensitive traffic is ${slaPct}%; retain human-in-the-loop control on these flows.`);
  } else {
    lines.push("No SLA-sensitive cluster detected in this sample window.");
  }

  if (metrics.estimatedHoursPerWeek >= 10) {
    lines.push(`Estimated workload is ${metrics.estimatedHoursPerWeek} hours/week, indicating stronger automation ROI potential.`);
  } else {
    lines.push(`Estimated workload is ${metrics.estimatedHoursPerWeek} hours/week; use this as a baseline before deeper implementation.`);
  }

  return lines;
}

function safeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function tableHtml(headers, rows) {
  if (!rows.length) {
    return "<small>No data available.</small>";
  }
  const thead = `<thead><tr>${headers.map((h) => `<th>${safeHtml(h)}</th>`).join("")}</tr></thead>`;
  const tbody = `<tbody>${rows.map((r) => `<tr>${r.map((v) => `<td>${safeHtml(v)}</td>`).join("")}</tr>`).join("")}</tbody>`;
  return `<table>${thead}${tbody}</table>`;
}

function barsHtml(title, rows) {
  if (!rows.length) {
    return `<article class="viz-card"><h4 class="viz-title">${safeHtml(title)}</h4><small>No data available.</small></article>`;
  }

  const bars = rows
    .map((row) => {
      const width = Math.max(2, Math.min(100, Number(row.value) || 0));
      return `
        <div class="viz-row">
          <div class="viz-row-head">
            <span>${safeHtml(row.label)}</span>
            <strong>${safeHtml(`${row.value}%`)}</strong>
          </div>
          <div class="viz-track">
            <div class="viz-fill" style="width:${width}%"></div>
          </div>
        </div>
      `;
    })
    .join("");

  return `<article class="viz-card"><h4 class="viz-title">${safeHtml(title)}</h4><div class="viz-bars">${bars}</div></article>`;
}

function renderReport(report) {
  const metrics = report.metrics;
  const categoryRows = Object.entries(metrics.categoryCounts)
    .sort((a, b) => b[1] - a[1])
    .map(([category, count]) => [
      category,
      String(count),
      `${metrics.categoryPercentages[category] || 0}%`,
      String(metrics.estimatedMinutesByCategory[category] || 0),
    ]);

  const natureRows = Object.entries(metrics.natureCounts).map(([name, count]) => [
    name,
    String(count),
    `${metrics.naturePercentages[name] || 0}%`,
  ]);

  const slaRows = metrics.slaClusters.map((x) => [x.category, String(x.count), `${x.shareOfSla}%`]);

  const categoryVizRows = Object.entries(metrics.categoryPercentages)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([label, value]) => ({ label, value }));

  const slaVizRows = metrics.slaClusters.map((x) => ({ label: x.category, value: x.shareOfSla }));

  const html = `
    <div class="report-grid">
      <article class="metric">
        <p class="metric-title">Inbound Volume</p>
        <p class="metric-value">${metrics.totalVolume}</p>
      </article>
      <article class="metric">
        <p class="metric-title">Observation Window</p>
        <p class="metric-value">${metrics.periodDays} day(s)</p>
      </article>
      <article class="metric">
        <p class="metric-title">Estimated Load</p>
        <p class="metric-value">${metrics.estimatedHoursPerWeek} hr/week</p>
      </article>
      <article class="metric">
        <p class="metric-title">SLA-sensitive Share</p>
        <p class="metric-value">${metrics.riskPercentages["SLA-sensitive"] || 0}%</p>
      </article>
    </div>

    <div class="visual-grid">
      ${barsHtml("Work Category Distribution", categoryVizRows)}
      ${barsHtml("SLA-sensitive Cluster Share", slaVizRows)}
    </div>

    <h3 class="section-title">1. Inbound Volume Snapshot</h3>
    <p>Total inbound items analyzed: <strong>${metrics.totalVolume}</strong></p>

    <h3 class="section-title">2. Work Category Breakdown</h3>
    ${tableHtml(["Work Category", "Volume", "% of Inbound", "Estimated Minutes"], categoryRows)}

    <h3 class="section-title">3. Repetitive vs Exception Work</h3>
    ${tableHtml(["Work Nature", "Volume", "% of Inbound"], natureRows)}

    <h3 class="section-title">4. Estimated Operational Load (hours/week)</h3>
    <p>Estimated total handling time in sample window: <strong>${metrics.estimatedTotalMinutes} minutes</strong></p>
    <p>Estimated weekly operational load: <strong>${metrics.estimatedHoursPerWeek} hours/week</strong></p>

    <h4 class="section-title">SLA-sensitive Work Clusters</h4>
    ${tableHtml(["Category", "SLA-sensitive Volume", "Share of SLA-sensitive"], slaRows)}

    <h3 class="section-title">5. Automation Leverage Summary</h3>
    <ul>${report.leverage.map((line) => `<li>${safeHtml(line)}</li>`).join("")}</ul>

    <h3 class="section-title">Conservative Assumptions</h3>
    <ul>
      <li>Diagnostic mode is read-only and one-time.</li>
      <li>Window cap used: ${report.assumptions.window}</li>
      <li>Handling-time defaults are conservative category baselines.</li>
      <li>Classifier is heuristic and directionally accurate (not perfect).</li>
    </ul>

    <small>Generated at ${safeHtml(report.generatedAt)}</small>
  `;

  el.reportRoot.innerHTML = html;
  el.reportPanel.classList.remove("hidden");
  el.reportPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

function exportPdf(report) {
  if (!window.jspdf || !window.jspdf.jsPDF) {
    throw new Error("jsPDF failed to load.");
  }

  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({ unit: "pt", format: "a4" });
  const margin = 42;
  const pageHeight = doc.internal.pageSize.getHeight();
  const pageWidth = doc.internal.pageSize.getWidth();
  const contentWidth = pageWidth - margin * 2;
  let y = margin;

  const writeParagraph = (text, size = 10.5, weight = "normal", gap = 10) => {
    doc.setFont("helvetica", weight);
    doc.setFontSize(size);
    const lines = doc.splitTextToSize(text, contentWidth);
    const height = lines.length * (size + 1);
    if (y + height > pageHeight - margin) {
      doc.addPage();
      y = margin;
    }
    doc.text(lines, margin, y);
    y += height + gap;
  };

  const table = (head, body) => {
    const startY = y;
    doc.autoTable({
      head: [head],
      body,
      startY,
      margin: { left: margin, right: margin },
      styles: { fontSize: 9.5, cellPadding: 5 },
      headStyles: { fillColor: [17, 126, 118] },
    });
    y = doc.lastAutoTable.finalY + 14;
    if (y > pageHeight - margin) {
      doc.addPage();
      y = margin;
    }
  };

  const metrics = report.metrics;
  const categoryRows = Object.entries(metrics.categoryCounts)
    .sort((a, b) => b[1] - a[1])
    .map(([category, count]) => [
      category,
      String(count),
      `${metrics.categoryPercentages[category] || 0}%`,
      String(metrics.estimatedMinutesByCategory[category] || 0),
    ]);

  const natureRows = Object.entries(metrics.natureCounts).map(([name, count]) => [
    name,
    String(count),
    `${metrics.naturePercentages[name] || 0}%`,
  ]);

  const slaRows = metrics.slaClusters.map((x) => [x.category, String(x.count), `${x.shareOfSla}%`]);

  writeParagraph("Operations Load Diagnostic Report", 16, "bold", 8);
  writeParagraph(`Generated: ${report.generatedAt}`, 10, "normal", 8);
  writeParagraph(`Total inbound items analyzed: ${metrics.totalVolume}`, 10.5, "normal", 4);
  writeParagraph(`Observation window: ${metrics.periodDays} day(s)`, 10.5, "normal", 10);

  writeParagraph("2. Work Category Breakdown", 12, "bold", 8);
  table(["Work Category", "Volume", "% of Inbound", "Estimated Minutes"], categoryRows);

  writeParagraph("3. Repetitive vs Exception Work", 12, "bold", 8);
  table(["Work Nature", "Volume", "% of Inbound"], natureRows);

  writeParagraph("4. Estimated Operational Load", 12, "bold", 8);
  writeParagraph(`Estimated total handling time in sample window: ${metrics.estimatedTotalMinutes} minutes`, 10.5, "normal", 3);
  writeParagraph(`Estimated weekly operational load: ${metrics.estimatedHoursPerWeek} hours/week`, 10.5, "normal", 10);

  writeParagraph("SLA-sensitive Work Clusters", 11, "bold", 8);
  table(["Category", "SLA-sensitive Volume", "Share of SLA-sensitive"], slaRows);

  writeParagraph("5. Automation Leverage Summary", 12, "bold", 8);
  report.leverage.forEach((line) => writeParagraph(`- ${line}`, 10.5, "normal", 2));

  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  doc.save(`operations_load_diagnostic_${stamp}.pdf`);
}

async function loadInputItems() {
  const mode = el.inputMode.value;
  const file = el.fileInput.files[0];
  const text = el.textInput.value.trim();

  if (file) {
    const raw = await file.text();
    if (mode === "csv") {
      return normalizeCsvItems(raw);
    }
    return normalizeTextBatchItems(raw);
  }

  if (text) {
    if (mode === "csv") {
      return normalizeCsvItems(text);
    }
    return normalizeTextBatchItems(text);
  }

  return [];
}

async function runDiagnostic() {
  setStatus("Processing inbound sample...");
  el.generateBtn.disabled = true;
  try {
    const lookbackDays = Math.max(1, Number(el.lookbackDays.value) || 14);
    const maxItems = Math.max(10, Number(el.maxItems.value) || 200);

    const rawItems = await loadInputItems();
    if (!rawItems.length) {
      throw new Error("No valid inbound items found. Upload a valid file or paste valid input text.");
    }

    const limited = limitItems(rawItems, lookbackDays, maxItems);
    const inbound = limited.items;
    const classified = inbound.map((item) => ({ item, classification: classifyItem(item) }));

    const metrics = aggregate(classified, lookbackDays);
    const leverage = leverageSummary(metrics);
    const anchorLabel = limited.anchorDate.toISOString().slice(0, 10);

    const report = {
      generatedAt: new Date().toLocaleString(),
      metrics,
      leverage,
      assumptions: {
        window: limited.appliedLookback
          ? `${lookbackDays} day lookback anchored to latest record (${anchorLabel}), max ${maxItems} items`
          : `${lookbackDays} day lookback requested; fallback used with latest ${inbound.length} records (anchor ${anchorLabel}).`,
      },
    };

    state.report = report;
    renderReport(report);
    el.pdfBtn.disabled = false;

    const statusMessage = limited.fallbackUsed
      ? `Diagnostic complete. ${metrics.totalVolume} items processed. Fallback applied because records did not match lookback window.`
      : `Diagnostic complete. ${metrics.totalVolume} items processed (lookback anchored to latest record: ${anchorLabel}).`;
    setStatus(statusMessage);
  } catch (err) {
    state.report = null;
    el.pdfBtn.disabled = true;
    el.reportPanel.classList.add("hidden");
    setStatus(err.message || "Failed to generate diagnostic.", true);
  } finally {
    el.generateBtn.disabled = false;
  }
}
async function loadSample() {
  setStatus("Loading sample CSV...");
  try {
    const response = await fetch("./examples/sample_inbound.csv", { cache: "no-store" });
    if (!response.ok) {
      throw new Error("Could not load sample file.");
    }
    const text = await response.text();
    el.inputMode.value = "csv";
    el.textInput.value = text;
    el.fileInput.value = "";
    updateFileMeta();
    setStatus("Sample loaded. Click 'Generate Diagnostic'.");
  } catch (err) {
    setStatus(err.message || "Failed to load sample.", true);
  }
}

el.generateBtn.addEventListener("click", runDiagnostic);
el.sampleBtn.addEventListener("click", loadSample);
el.fileInput.addEventListener("change", updateFileMeta);

el.pdfBtn.addEventListener("click", () => {
  if (!state.report) {
    setStatus("Generate a diagnostic first.", true);
    return;
  }
  try {
    exportPdf(state.report);
    setStatus("PDF report downloaded.");
  } catch (err) {
    setStatus(err.message || "Failed to generate PDF.", true);
  }
});

updateFileMeta();
setStatus("Upload a file or load the sample to begin. Build: 2026-02-08-2.");



