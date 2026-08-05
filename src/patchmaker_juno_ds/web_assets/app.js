const $ = (selector) => document.querySelector(selector);
let currentPatch = null;
let currentHistoryId = null;
let toastTimer = null;

const fields = {
  baseUrl: $("#base-url"), model: $("#model"), apiKey: $("#api-key"),
  inputPort: $("#input-port"), outputPort: $("#output-port"), request: $("#request")
};

fields.baseUrl.value = "https://openrouter.ai/api/v1";
fields.model.value = "openrouter/free";

function resetConnectionStatus() {
  const node = $("#connection-result");
  node.className = "connection-result";
  node.querySelector("span").textContent = "Connection not tested";
}

function clearGenerationError() {
  const node = $("#generation-error");
  node.classList.add("hidden");
  node.querySelector("span").textContent = "";
}

function showGenerationError(message) {
  const node = $("#generation-error");
  node.querySelector("span").textContent = message;
  node.classList.remove("hidden");
}

[fields.baseUrl, fields.model, fields.apiKey].forEach(field => field.addEventListener("input", resetConnectionStatus));

async function loadConfiguration() {
  const data = await api("/api/configuration", {});
  fields.baseUrl.value = data.base_url;
  fields.model.value = data.model;
  if (data.api_key_configured) {
    fields.apiKey.placeholder = "Saved key configured in .env";
    $("#key-help").textContent = "A saved key is configured in the local .env file. Paste a replacement only when you want to change it.";
  }
}

async function saveConfiguration() {
  const node = $("#save-result");
  node.className = "save-result";
  node.textContent = "Saving to local .env…";
  try {
    const data = await api("/api/save-configuration", {
      base_url: fields.baseUrl.value, model: fields.model.value, api_key: fields.apiKey.value
    });
    fields.apiKey.value = "";
    fields.apiKey.placeholder = data.api_key_configured ? "Saved key configured in .env" : "No key configured";
    $("#key-help").textContent = data.api_key_configured
      ? "A saved key is configured in the local .env file. Paste a replacement only when you want to change it."
      : "No API key is saved. Paste one above and save again if your endpoint requires authentication.";
    node.className = "save-result success";
    node.textContent = `${data.message} · ${data.storage}`;
    resetConnectionStatus();
    toast("Model settings saved to .env");
  } catch (error) {
    node.className = "save-result failure";
    node.textContent = error.message;
  }
}

function status(message, type = "ready") {
  const node = $("#app-status");
  node.className = `status ${type === "ready" ? "" : type}`;
  node.querySelector("span").textContent = message;
}

function toast(message, error = false) {
  const node = $("#toast");
  node.textContent = message;
  node.className = `toast show${error ? " error" : ""}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => node.className = "toast", 4200);
}

async function api(path, payload) {
  status("Working…", "busy");
  try {
    const options = payload === undefined ? {} : {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)
    };
    const response = await fetch(path, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
    status("Ready");
    return data;
  } catch (error) {
    status("Needs attention", "error");
    toast(error.message, true);
    throw error;
  }
}

function metric(label, value) {
  const node = document.createElement("div");
  node.className = "metric";
  const small = document.createElement("small"); small.textContent = label;
  const strong = document.createElement("strong"); strong.textContent = value;
  node.append(small, strong);
  return node;
}

function toneRow(label, value) {
  const row = document.createElement("div"); row.className = "tone-row";
  const name = document.createElement("span"); name.textContent = label;
  const data = document.createElement("b"); data.textContent = value;
  row.append(name, data); return row;
}

function renderPatch(patch, explanation = "Patch loaded and ready to refine.", record = null) {
  currentPatch = patch;
  currentHistoryId = record ? record.id : null;
  const common = patch.parameters.common;
  $("#empty-state").classList.add("hidden");
  $("#result-card").classList.remove("hidden");
  $("#loaded-patch").classList.remove("hidden");
  $("#loaded-name").textContent = patch.name;
  $("#loaded-category").textContent = patch.category_name;
  $("#patch-name").textContent = patch.name;
  $("#explanation").textContent = explanation;
  $("#current-version").textContent = record
    ? `Saved ${formatDate(record.created_at)}`
    : "Unsaved working patch";
  const strip = $("#common-parameters"); strip.replaceChildren(
    metric("Category", patch.category_name), metric("Level", common.level),
    metric("Cutoff offset", signed(common.cutoff_offset)), metric("Attack offset", signed(common.attack_offset)),
    metric("Release offset", signed(common.release_offset)), metric("Analog feel", common.analog_feel)
  );
  const grid = $("#tone-grid"); grid.replaceChildren();
  patch.parameters.tones.forEach((tone, index) => {
    const card = document.createElement("article"); card.className = `tone-card${tone.enabled ? "" : " off"}`;
    const title = document.createElement("div"); title.className = "tone-title";
    const name = document.createElement("strong"); name.textContent = `TONE ${index + 1}`;
    const state = document.createElement("span"); state.textContent = tone.enabled ? "ACTIVE" : "OFF";
    title.append(name, state); card.append(title,
      toneRow("Wave", tone.wave_number), toneRow("Level", tone.level),
      toneRow("Filter", tone.filter_type), toneRow("Cutoff", tone.cutoff),
      toneRow("Resonance", tone.resonance), toneRow("Amp attack", tone.amp_attack),
      toneRow("Amp release", tone.amp_release), toneRow("LFO", tone.lfo1_waveform)
    );
    grid.append(card);
  });
}

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString([], {dateStyle: "medium", timeStyle: "short"});
}

async function refreshHistory() {
  const data = await api("/api/history", {});
  const list = $("#history-list");
  $("#history-count").textContent = `${data.patches.length} ${data.patches.length === 1 ? "patch" : "patches"}`;
  list.replaceChildren();
  if (!data.patches.length) {
    const empty = document.createElement("div");
    empty.className = "history-empty";
    empty.textContent = "Generated patches will be saved here automatically.";
    list.append(empty);
    return;
  }
  const duplicateCounts = data.patches.reduce((counts, record) => {
    counts.set(record.name, (counts.get(record.name) || 0) + 1);
    return counts;
  }, new Map());
  const remainingVersions = new Map(duplicateCounts);
  data.patches.forEach(record => {
    const item = document.createElement("article");
    item.className = `history-item${record.id === currentHistoryId ? " current" : ""}`;
    item.tabIndex = 0; item.setAttribute("role", "button");
    const header = document.createElement("header");
    const version = remainingVersions.get(record.name);
    remainingVersions.set(record.name, version - 1);
    const displayName = duplicateCounts.get(record.name) > 1
      ? `${record.name} · v${version}`
      : record.name;
    const name = document.createElement("strong"); name.textContent = displayName;
    const controls = document.createElement("span"); controls.className = "history-controls";
    const time = document.createElement("time"); time.textContent = formatDate(record.created_at);
    const remove = document.createElement("button"); remove.className = "history-delete";
    remove.type = "button"; remove.title = `Delete ${displayName}`; remove.setAttribute("aria-label", remove.title);
    remove.textContent = "×";
    remove.addEventListener("click", event => {
      event.stopPropagation();
      deleteHistoryPatch(record).catch(() => {});
    });
    remove.addEventListener("keydown", event => event.stopPropagation());
    controls.append(time, remove); header.append(name, controls);
    const request = document.createElement("p"); request.textContent = record.request;
    const category = document.createElement("small"); category.textContent = record.category_name;
    item.append(header, request, category);
    item.addEventListener("click", () => loadHistoryPatch(record.id).catch(() => {}));
    item.addEventListener("keydown", event => {
      if (["Enter", " "].includes(event.key)) { event.preventDefault(); loadHistoryPatch(record.id).catch(() => {}); }
    });
    list.append(item);
  });
}

async function deleteHistoryPatch(record) {
  if (!confirm(`Remove ${record.name} from the local patch library? This cannot be undone.`)) return;
  const data = await api("/api/history/delete", {id: record.id});
  if (currentHistoryId === record.id) {
    currentHistoryId = null;
    $("#current-version").textContent = "Unsaved working patch";
  }
  await refreshHistory();
  toast(data.message);
}

async function loadHistoryPatch(id) {
  const data = await api("/api/history/get", {id});
  fields.request.value = data.record.request;
  renderPatch(data.patch, data.message, data.record);
  await refreshHistory();
  toast("Saved patch loaded");
}

const signed = (value) => value > 0 ? `+${value}` : String(value);

async function loadDemo() {
  const data = await api("/api/demo", {}); renderPatch(data.patch, "Neutral demo patch loaded. Try describing a variation."); toast("Demo patch loaded");
}

async function randomizePrompt(showToast = true) {
  const data = await api("/api/random-prompt", {});
  fields.request.value = data.prompt;
  if (showToast) toast("New sound idea generated");
}

async function testConnection() {
  const node = $("#connection-result");
  node.className = "connection-result";
  node.querySelector("span").textContent = "Testing endpoint, model, and key…";
  try {
    const data = await api("/api/test-connection", {
      base_url: fields.baseUrl.value, model: fields.model.value, api_key: fields.apiKey.value
    });
    const requestedModel = fields.model.value.trim();
    if (requestedModel === "openrouter/free" && data.model && data.model !== requestedModel) {
      fields.model.value = data.model;
    }
    node.className = "connection-result success";
    node.querySelector("span").textContent = requestedModel === "openrouter/free" && data.model !== requestedModel
      ? `${data.message} · pinned ${data.model}`
      : `${data.message} · ${data.model}`;
    toast("Model connection verified");
  } catch (error) {
    node.className = "connection-result failure";
    node.querySelector("span").textContent = error.message;
  }
}

async function loadFile(file) {
  try {
    const patch = JSON.parse(await file.text());
    const data = await api("/api/validate", {patch}); renderPatch(data.patch); toast(data.message);
  } catch (error) { if (!(error instanceof SyntaxError)) return; toast(`Invalid JSON: ${error.message}`, true); }
}

async function refine() {
  if (!currentPatch) return toast("Load a starting patch first", true);
  if (!fields.request.value.trim()) return toast("Describe the sound you want", true);
  clearGenerationError();
  try {
    const data = await api("/api/refine", {
      patch: currentPatch, request: fields.request.value,
      base_url: fields.baseUrl.value, model: fields.model.value, api_key: fields.apiKey.value,
      parent_id: currentHistoryId
    });
    renderPatch(data.patch, data.message, data.record);
    await refreshHistory();
    toast("Variation generated and saved");
  } catch (error) {
    showGenerationError(error.message);
    throw error;
  }
}

async function refreshPorts() {
  const data = await api("/api/ports");
  fillSelect(fields.inputPort, data.inputs, "No MIDI input");
  fillSelect(fields.outputPort, data.outputs, "No MIDI output");
  toast(`Found ${data.inputs.length} input and ${data.outputs.length} output ports`);
}

function fillSelect(select, values, empty) {
  const prior = select.value; select.replaceChildren();
  const option = document.createElement("option"); option.value = ""; option.textContent = empty; select.append(option);
  values.forEach(value => { const item = document.createElement("option"); item.value = value; item.textContent = value; select.append(item); });
  if (values.includes(prior)) select.value = prior;
}

async function readHardware() {
  requirePorts();
  const data = await api("/api/read", {input_port: fields.inputPort.value, output_port: fields.outputPort.value});
  renderPatch(data.patch, data.message); toast(data.message);
}

async function sendHardware() {
  if (!currentPatch) return toast("Load or generate a patch first", true);
  requirePorts();
  if (!confirm("Send this patch to the JUNO-DS temporary edit buffer? This will not save over a user patch.")) return;
  const data = await api("/api/write", {patch: currentPatch, input_port: fields.inputPort.value, output_port: fields.outputPort.value, confirm: true});
  toast(data.message);
}

function requirePorts() {
  if (!fields.inputPort.value || !fields.outputPort.value) throw new Error("Select both JUNO MIDI ports first");
}

function downloadPatch() {
  if (!currentPatch) return;
  const blob = new Blob([JSON.stringify(currentPatch, null, 2) + "\n"], {type: "application/json"});
  const anchor = document.createElement("a"); anchor.href = URL.createObjectURL(blob);
  anchor.download = `${currentPatch.name.trim().replace(/[^a-z0-9]+/gi, "-").toLowerCase() || "juno-patch"}.json`;
  anchor.click(); URL.revokeObjectURL(anchor.href); toast("Patch JSON downloaded");
}

const dropzone = $("#dropzone");
dropzone.addEventListener("click", () => $("#patch-file").click());
dropzone.addEventListener("keydown", event => { if (["Enter", " "].includes(event.key)) $("#patch-file").click(); });
$("#patch-file").addEventListener("change", event => event.target.files[0] && loadFile(event.target.files[0]));
["dragenter", "dragover"].forEach(name => dropzone.addEventListener(name, event => { event.preventDefault(); dropzone.classList.add("drag"); }));
["dragleave", "drop"].forEach(name => dropzone.addEventListener(name, event => { event.preventDefault(); dropzone.classList.remove("drag"); }));
dropzone.addEventListener("drop", event => event.dataTransfer.files[0] && loadFile(event.dataTransfer.files[0]));

$("#demo-button").addEventListener("click", () => loadDemo().catch(() => {}));
$("#randomize-prompt").addEventListener("click", () => randomizePrompt().catch(() => {}));
$("#save-configuration").addEventListener("click", saveConfiguration);
$("#test-connection").addEventListener("click", testConnection);
$("#refine-button").addEventListener("click", () => refine().catch(() => {}));
$("#refresh-ports").addEventListener("click", () => refreshPorts().catch(() => {}));
$("#read-button").addEventListener("click", () => readHardware().catch(error => toast(error.message, true)));
$("#send-button").addEventListener("click", () => sendHardware().catch(error => toast(error.message, true)));
$("#download-button").addEventListener("click", downloadPatch);
$("#refresh-history").addEventListener("click", () => refreshHistory().catch(() => {}));
document.querySelectorAll("[data-prompt]").forEach(button => button.addEventListener("click", () => fields.request.value = button.dataset.prompt));

// The GUI is immediately usable: it always starts with both a neutral,
// validated patch and a fully formed sound description. Both remain editable.
Promise.all([loadDemo(), randomizePrompt(false), loadConfiguration(), refreshHistory()]).catch(() => {});
