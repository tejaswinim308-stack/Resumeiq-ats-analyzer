(() => {
  "use strict";

  const MAX_FILE_MB = 10;
  const MIN_JD_LENGTH = 50;

  const els = {
    views: {
      upload: document.getElementById("view-upload"),
      loading: document.getElementById("view-loading"),
      dashboard: document.getElementById("view-dashboard"),
      "empty-history": document.getElementById("view-empty-history"),
    },
    navLinks: document.querySelectorAll(".nav-link"),
    apiStatusText: document.getElementById("apiStatusText"),

    form: document.getElementById("analyzeForm"),
    dropzone: document.getElementById("dropzone"),
    resumeInput: document.getElementById("resumeInput"),
    dropzoneEmpty: document.getElementById("dropzoneEmpty"),
    dropzoneFile: document.getElementById("dropzoneFile"),
    fileName: document.getElementById("fileName"),
    fileSize: document.getElementById("fileSize"),
    removeFileBtn: document.getElementById("removeFileBtn"),
    fileError: document.getElementById("fileError"),

    jobDescription: document.getElementById("jobDescription"),
    jdCharCount: document.getElementById("jdCharCount"),
    jdError: document.getElementById("jdError"),

    analyzeBtn: document.getElementById("analyzeBtn"),
    apiError: document.getElementById("apiError"),

    scanFileName: document.getElementById("scanFileName"),
    steps: document.querySelectorAll(".step"),

    newAnalysisBtn: document.getElementById("newAnalysisBtn"),
  };

  let selectedFile = null;

  function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // ---------------- View switching ----------------
  function showView(name) {
    Object.entries(els.views).forEach(([key, el]) => {
      if (el) el.classList.toggle("active", key === name);
    });
    els.navLinks.forEach((link) => {
      link.classList.toggle("active", link.dataset.view === name);
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  els.navLinks.forEach((link) => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const target = link.dataset.view;
      if (target === "dashboard" && !window.__lastAnalysis) {
        showView("empty-history");
        return;
      }
      showView(target);
    });
  });

  els.newAnalysisBtn.addEventListener("click", () => {
    resetForm();
    showView("upload");
  });

  // ---------------- Health check ----------------
  API.health()
    .then((data) => {
      els.apiStatusText.textContent = data.gemini_configured ? "Ready" : "Not configured";
      els.apiStatusText.style.color = data.gemini_configured ? "var(--secondary)" : "var(--tertiary)";
    })
    .catch(() => {
      els.apiStatusText.textContent = "Offline";
      els.apiStatusText.style.color = "var(--error)";
    });

  // ---------------- Dropzone / file selection ----------------
  els.dropzone.addEventListener("click", () => els.resumeInput.click());
  els.dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    els.dropzone.classList.add("dragover");
  });
  els.dropzone.addEventListener("dragleave", () => els.dropzone.classList.remove("dragover"));
  els.dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    els.dropzone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });
  els.resumeInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) handleFileSelected(e.target.files[0]);
  });
  els.removeFileBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    selectedFile = null;
    els.resumeInput.value = "";
    els.dropzoneEmpty.hidden = false;
    els.dropzoneFile.hidden = true;
    hideError(els.fileError);
  });

  function handleFileSelected(file) {
    hideError(els.fileError);
    const ext = (file.name.split(".").pop() || "").toLowerCase();
    if (ext !== "pdf") {
      showError(els.fileError, "Only PDF files are accepted.");
      return;
    }
    if (file.size === 0) {
      showError(els.fileError, "This file is empty.");
      return;
    }
    if (file.size > MAX_FILE_MB * 1024 * 1024) {
      showError(els.fileError, `File is too large (${(file.size / (1024 * 1024)).toFixed(1)} MB). Maximum is ${MAX_FILE_MB} MB.`);
      return;
    }
    selectedFile = file;
    els.fileName.textContent = file.name;
    els.fileSize.textContent = formatBytes(file.size);
    els.dropzoneEmpty.hidden = true;
    els.dropzoneFile.hidden = false;
  }

  function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  }

  // ---------------- Job description ----------------
  els.jobDescription.addEventListener("input", () => {
    const len = els.jobDescription.value.length;
    els.jdCharCount.textContent = `${len} chars`;
    if (len > 0) hideError(els.jdError);
  });

  function showError(el, message) {
    el.textContent = message;
    el.hidden = false;
  }
  function hideError(el) {
    el.hidden = true;
    el.textContent = "";
  }

  // ---------------- Submit ----------------
  els.form.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideError(els.fileError);
    hideError(els.jdError);
    els.apiError.hidden = true;

    let valid = true;
    if (!selectedFile) {
      showError(els.fileError, "Please select a PDF resume to upload.");
      valid = false;
    }
    const jd = els.jobDescription.value.trim();
    if (!jd) {
      showError(els.jdError, "Job description is required.");
      valid = false;
    } else if (jd.length < MIN_JD_LENGTH) {
      showError(els.jdError, `Job description is too short. Please provide at least ${MIN_JD_LENGTH} characters.`);
      valid = false;
    }
    if (!valid) return;

    runAnalysis(selectedFile, jd);
  });

  async function runAnalysis(file, jobDescription) {
    els.analyzeBtn.disabled = true;
    els.scanFileName.textContent = file.name;
    showView("loading");
    animateSteps();

    try {
      const result = await API.analyze(file, jobDescription);
      window.__lastAnalysis = result;
      renderDashboard(result);
      showView("dashboard");
    } catch (err) {
      showView("upload");
      els.apiError.hidden = false;
      els.apiError.textContent = friendlyErrorMessage(err);
    } finally {
      els.analyzeBtn.disabled = false;
      clearStepAnimation();
    }
  }

  function friendlyErrorMessage(err) {
    const map = {
      network_error: "Could not reach the ResumeIQ backend. Make sure it's running and reachable.",
      configuration_error: "The analysis service isn't fully configured on the server yet (missing Gemini API key).",
      gemini_timeout: "The analysis timed out. Please try again.",
      gemini_invalid_response: "The analysis service returned an unexpected response. Please try again.",
    };
    return map[err.code] || err.message || "Something went wrong. Please try again.";
  }

  let stepInterval = null;
  function animateSteps() {
    clearStepAnimation();
    let current = 0;
    els.steps.forEach((s, i) => {
      s.classList.toggle("done", false);
      s.classList.toggle("active", i === 0);
    });
    stepInterval = setInterval(() => {
      current = (current + 1) % (els.steps.length + 1);
      els.steps.forEach((s, i) => {
        s.classList.toggle("done", i < current);
        s.classList.toggle("active", i === current);
      });
    }, 900);
  }
  function clearStepAnimation() {
    if (stepInterval) clearInterval(stepInterval);
    stepInterval = null;
  }

  function resetForm() {
    selectedFile = null;
    els.resumeInput.value = "";
    els.dropzoneEmpty.hidden = false;
    els.dropzoneFile.hidden = true;
    els.jobDescription.value = "";
    els.jdCharCount.textContent = "0 chars";
    hideError(els.fileError);
    hideError(els.jdError);
    els.apiError.hidden = true;
  }

  // ---------------- Dashboard rendering ----------------
  function scoreColor(pointsRatio) {
    if (pointsRatio >= 0.8) return "var(--secondary)";
    if (pointsRatio >= 0.6) return "var(--tertiary)";
    return "var(--error)";
  }

  function renderDashboard(data) {
    document.getElementById("dashCandidateName").textContent = data.resume.name || "Candidate";
    document.getElementById("dashRole").textContent = data.job.title || "Target Role";

    // Score ring
    const overall = data.score.overall;
    const ring = document.getElementById("scoreRing");
    const circumference = 2 * Math.PI * 52;
    const offset = circumference * (1 - overall / 100);
    ring.style.strokeDasharray = `${circumference}`;
    ring.style.strokeDashoffset = `${offset}`;
    ring.style.stroke = scoreColor(overall / 100);
    document.getElementById("scoreOverall").textContent = overall;

    // Category breakdown
    const breakdown = data.score_breakdown || {};
    const breakdownEl = document.getElementById("scoreBreakdown");
    breakdownEl.innerHTML = "";
    Object.entries(breakdown).forEach(([key, val]) => {
      const ratio = val.max ? val.points / val.max : 0;
      const row = document.createElement("div");
      row.className = "score-row";
      row.title = val.explanation || "";
      row.innerHTML = `
        <span class="score-row-label">${escapeHtml(key.replace(/_/g, " "))}</span>
        <div class="score-bar-track"><div class="score-bar-fill" style="width:${Math.round(ratio * 100)}%; background:${scoreColor(ratio)}"></div></div>
        <span class="score-row-val">${escapeHtml(String(val.points))}/${escapeHtml(String(val.max))}</span>
      `;
      breakdownEl.appendChild(row);
    });

    // Strengths / improvements
    fillPillList("strengthsList", data.strengths, "No standout strengths identified yet.");
    fillPillList("improvementsList", data.improvements, "No major issues found — nice work.");

    // Skills
    fillChips("skillsMatched", data.skills.matched, "chip-good", "None matched.");
    fillChips("skillsMissing", data.skills.missing, "chip-bad", "Nothing missing.");
    fillChips("skillsRecommended", data.skills.recommended, "chip-rec", "No safe additions found.");

    // Keywords
    fillChips("keywordsMatched", data.keywords.matched, "chip-good", "None matched.");
    fillChips("keywordsMissing", data.keywords.missing, "chip-bad", "Nothing missing.");

    // Sections
    const sectionGrid = document.getElementById("sectionGrid");
    sectionGrid.innerHTML = "";
    (data.sections || []).forEach((s) => {
      const ratio = s.score / 10;
      const card = document.createElement("div");
      card.className = "section-card";
      card.innerHTML = `
        <div class="section-card-head">
          <span class="section-card-name">${escapeHtml(s.section)}</span>
          <span class="section-card-score mono">${escapeHtml(String(s.score))}/10</span>
        </div>
        <div class="section-card-bar"><div class="section-card-bar-fill" style="width:${ratio * 100}%; background:${scoreColor(ratio)}"></div></div>
        <p class="section-card-notes">${escapeHtml(s.notes || "")}</p>
      `;
      sectionGrid.appendChild(card);
    });

    // Recommendations
    const recList = document.getElementById("recommendationsList");
    recList.innerHTML = "";
    (data.recommendations || []).forEach((r) => {
      const priorityClass = { High: "tag-error", Medium: "tag-warning", Low: "tag-neutral" }[r.priority] || "tag-neutral";
      const card = document.createElement("div");
      card.className = "rec-card";
      card.innerHTML = `
        <div class="rec-card-head">
          <span class="rec-title">${escapeHtml(r.title)}</span>
          <span class="tag ${priorityClass}">${escapeHtml(r.priority)}</span>
        </div>
        <p class="rec-reason">${escapeHtml(r.reason)}</p>
        <p class="rec-action">${escapeHtml(r.suggested_action)}</p>
      `;
      recList.appendChild(card);
    });
  }

  function fillPillList(elId, items, emptyText) {
    const el = document.getElementById(elId);
    el.innerHTML = "";
    if (!items || items.length === 0) {
      const li = document.createElement("li");
      li.className = "empty-note";
      li.textContent = emptyText;
      el.appendChild(li);
      return;
    }
    items.forEach((text) => {
      const li = document.createElement("li");
      li.textContent = text;
      el.appendChild(li);
    });
  }

  function fillChips(elId, items, chipClass, emptyText) {
    const el = document.getElementById(elId);
    el.innerHTML = "";
    if (!items || items.length === 0) {
      const span = document.createElement("span");
      span.className = "chip";
      span.textContent = emptyText;
      el.appendChild(span);
      return;
    }
    items.forEach((text) => {
      const span = document.createElement("span");
      span.className = `chip ${chipClass}`;
      span.textContent = text;
      el.appendChild(span);
    });
  }
})();
