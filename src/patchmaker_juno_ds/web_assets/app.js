const $ = (selector) => document.querySelector(selector);
let currentPatch = null;
let toastTimer = null;

const fields = {
  baseUrl: $("#base-url"), model: $("#model"), apiKey: $("#api-key"),
  inputPort: $("#input-port"), outputPort: $("#output-port"), request: $("#request")
};

fields.baseUrl.value = localStorage.getItem("patchmaker.baseUrl") || "";
fields.model.value = localStorage.getItem("patchmaker.model") || "";
fields.baseUrl.addEventListener("change", () => localStorage.setItem("patchmaker.baseUrl", fields.baseUrl.value));
fields.model.addEventListener("change", () => localStorage.setItem("patchmaker.model", fields.model.value));

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

function renderPatch(patch, explanation = "Patch loaded and ready to refine.") {
  currentPatch = patch;
  const common = patch.parameters.common;
  $("#empty-state").classList.add("hidden");
  $("#result-card").classList.remove("hidden");
  $("#loaded-patch").classList.remove("hidden");
  $("#loaded-name").textContent = patch.name;
  $("#loaded-category").textContent = patch.category_name;
  $("#patch-name").textContent = patch.name;
  $("#explanation").textContent = explanation;
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

const signed = (value) => value > 0 ? `+${value}` : String(value);

async function loadDemo() {
  const data = await api("/api/demo", {}); renderPatch(data.patch, "Neutral demo patch loaded. Try describing a variation."); toast("Demo patch loaded");
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
  const data = await api("/api/refine", {
    patch: currentPatch, request: fields.request.value,
    base_url: fields.baseUrl.value, model: fields.model.value, api_key: fields.apiKey.value
  });
  renderPatch(data.patch, data.message); toast("Variation generated");
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
$("#refine-button").addEventListener("click", () => refine().catch(() => {}));
$("#refresh-ports").addEventListener("click", () => refreshPorts().catch(() => {}));
$("#read-button").addEventListener("click", () => readHardware().catch(error => toast(error.message, true)));
$("#send-button").addEventListener("click", () => sendHardware().catch(error => toast(error.message, true)));
$("#download-button").addEventListener("click", downloadPatch);
document.querySelectorAll("[data-prompt]").forEach(button => button.addEventListener("click", () => fields.request.value = button.dataset.prompt));
