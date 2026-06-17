const placements = document.querySelector("#placements");
const previewBtn = document.querySelector("#previewBtn");
const applyBtn = document.querySelector("#applyBtn");
const moveInput = document.querySelector("#move");
const dryRunInput = document.querySelector("#dryRun");
const previewRows = document.querySelector("#previewRows");
const summary = document.querySelector("#summary");
const output = document.querySelector("#output");
const seriesList = document.querySelector("#seriesList");
const questionList = document.querySelector("#questionList");
const viewerTitle = document.querySelector("#viewerTitle");
const viewerCount = document.querySelector("#viewerCount");
const modeNotice = document.querySelector("#modeNotice");

let previewTimer = null;
let selectedSerie = null;

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function postJson(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    throw data;
  }
  return data;
}

function renderPreview(data) {
  const rows = [];

  for (const item of data.placements) {
    rows.push(`
      <tr>
        <td>${item.line}</td>
        <td>${item.question}</td>
        <td>serie${item.serie}</td>
        <td><span class="${item.duplicate ? "badge warn" : "badge ok"}">${item.duplicate ? "doublon dans la saisie" : "prêt"}</span></td>
      </tr>
    `);
  }

  for (const item of data.errors) {
    rows.push(`
      <tr class="errorRow">
        <td>${item.line}</td>
        <td colspan="2">${escapeHtml(item.text)}</td>
        <td><span class="badge error">${escapeHtml(item.message)}</span></td>
      </tr>
    `);
  }

  previewRows.innerHTML = rows.join("") || `<tr><td colspan="4" class="empty">Aucune ligne à traiter</td></tr>`;
  summary.innerHTML = `
    <span>${data.placements.length} ligne${data.placements.length > 1 ? "s" : ""} prête${data.placements.length > 1 ? "s" : ""}</span>
    <span>${data.errors.length} erreur${data.errors.length > 1 ? "s" : ""}</span>
  `;
}

async function preview() {
  try {
    const data = await postJson("/api/preview", { text: placements.value });
    renderPreview(data);
    return data;
  } catch (error) {
    output.textContent = error.error || "Erreur de prévisualisation";
    throw error;
  }
}

function renderApplyResult(data) {
  const prefix = data.dryRun ? "[simulation] " : "";
  const lines = [];

  for (const item of data.added) {
    lines.push(`${prefix}${item.question} -> serie${item.serie}`);
  }
  for (const item of data.skipped) {
    lines.push(`${prefix}${item.question} -> serie${item.serie} ignoré (${item.reason})`);
  }
  for (const item of data.moved) {
    lines.push(`${prefix}${item.question} retiré de ${item.from}`);
  }

  output.textContent = lines.join("\n") || "Aucun changement.";
}

async function apply() {
  output.textContent = "";
  applyBtn.disabled = true;
  previewBtn.disabled = true;

  try {
    const data = await postJson("/api/apply", {
      text: placements.value,
      move: moveInput.checked,
      dryRun: dryRunInput.checked,
    });
    renderApplyResult(data);
    await loadStatus();
    if (selectedSerie) {
      await loadSerie(selectedSerie);
    }
  } catch (error) {
    if (error.errors) {
      renderPreview({ placements: [], errors: error.errors });
      output.textContent = "Corrige les lignes en erreur avant d’appliquer.";
    } else {
      output.textContent = error.error || "Erreur pendant l’application.";
    }
  } finally {
    applyBtn.disabled = false;
    previewBtn.disabled = false;
  }
}

async function loadStatus() {
  const response = await fetch("/api/status");
  const data = await response.json();
  seriesList.innerHTML = data.series
    .map((serie) => `
      <button class="serieLine${serie.id === selectedSerie ? " selected" : ""}" type="button" data-serie="${escapeHtml(serie.id)}">
        <span>${escapeHtml(serie.id)}</span>
        <strong>${serie.count}</strong>
      </button>
    `)
    .join("");
}

function renderSerie(data) {
  viewerTitle.textContent = data.id;
  viewerCount.textContent = `${data.count} question${data.count > 1 ? "s" : ""}`;

  questionList.innerHTML = data.questions
    .map((question) => `
      <article class="questionItem">
        <div class="questionMeta">
          <strong>${question.id}</strong>
          <span>${escapeHtml(question.scene || "")}</span>
        </div>
        <p>${escapeHtml(question.text || "(sans texte)")}</p>
      </article>
    `)
    .join("") || `<p>Aucune question dans cette série.</p>`;
}

async function loadSerie(serieId) {
  selectedSerie = serieId;
  questionList.innerHTML = `<p>Chargement...</p>`;
  await loadStatus();

  try {
    const response = await fetch(`/api/series/${encodeURIComponent(serieId)}`);
    const data = await response.json();
    if (!response.ok) {
      throw data;
    }
    renderSerie(data);
  } catch (error) {
    viewerTitle.textContent = serieId;
    viewerCount.textContent = "erreur";
    questionList.innerHTML = `<p>${escapeHtml(error.error || "Impossible de charger la série.")}</p>`;
  }
}

function updateModeNotice() {
  if (dryRunInput.checked) {
    modeNotice.className = "notice testMode";
    modeNotice.textContent = "Simulation active : aucun fichier JSON ne sera modifié.";
    applyBtn.textContent = "Simuler";
  } else {
    modeNotice.className = "notice writeMode";
    modeNotice.textContent = "Écriture active : Appliquer modifiera les fichiers JSON.";
    applyBtn.textContent = "Appliquer";
  }
}

placements.addEventListener("input", () => {
  window.clearTimeout(previewTimer);
  previewTimer = window.setTimeout(preview, 220);
});
previewBtn.addEventListener("click", preview);
applyBtn.addEventListener("click", apply);
dryRunInput.addEventListener("change", updateModeNotice);
seriesList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-serie]");
  if (button) {
    loadSerie(button.dataset.serie);
  }
});

updateModeNotice();
preview();
loadStatus().then(() => {
  const firstSerie = seriesList.querySelector("[data-serie]");
  if (firstSerie) {
    loadSerie(firstSerie.dataset.serie);
  }
});
