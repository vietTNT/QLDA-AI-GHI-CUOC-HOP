const state = {
  mediaRecorder: null,
  audioChunks: [],
  audioBlob: null,
  audioUrl: null,
  currentJobId: null,
  audioContext: null,
  analyser: null,
  animationFrame: null,
  startedAt: null,
  timerInterval: null,
  latestResult: null,
  speakerLabels: {},
};

const els = {
  body: document.body,
  modelStatus: document.querySelector("#modelStatus"),
  recordBtn: document.querySelector("#recordBtn"),
  stopBtn: document.querySelector("#stopBtn"),
  processBtn: document.querySelector("#processBtn"),
  fileInput: document.querySelector("#fileInput"),
  playback: document.querySelector("#playback"),
  timer: document.querySelector("#timer"),
  waveform: document.querySelector("#waveform"),
  recordState: document.querySelector("#recordState"),
  pipeline: document.querySelector("#pipeline"),
  languageSelect: document.querySelector("#languageSelect"),
  translateSelect: document.querySelector("#translateSelect"),
  speakerCountSelect: document.querySelector("#speakerCountSelect"),
  sttQualitySelect: document.querySelector("#sttQualitySelect"),
  meetingContextInput: document.querySelector("#meetingContextInput"),
  diarizationToggle: document.querySelector("#diarizationToggle"),
  summaryToggle: document.querySelector("#summaryToggle"),
  llmToggle: document.querySelector("#llmToggle"),
  summaryOutput: document.querySelector("#summaryOutput"),
  warningOutput: document.querySelector("#warningOutput"),
  transcriptOutput: document.querySelector("#transcriptOutput"),
  speakerLabelControls: document.querySelector("#speakerLabelControls"),
  speakerOutput: document.querySelector("#speakerOutput"),
  translationOutput: document.querySelector("#translationOutput"),
  copyBtn: document.querySelector("#copyBtn"),
  pdfBtn: document.querySelector("#pdfBtn"),
  downloadBtn: document.querySelector("#downloadBtn"),
};

const ctx = els.waveform.getContext("2d");

function setStatus(text, kind = "pending") {
  els.modelStatus.innerHTML = `<span class="dot ${kind}"></span><span>${text}</span>`;
}

function setRecordState(text) {
  const labels = {
    Ready: "Sẵn sàng",
    Recorded: "Đã ghi",
    Recording: "Đang ghi",
    Processing: "Đang xử lý",
    Complete: "Hoàn tất",
    Copied: "Đã sao chép",
    Downloaded: "Đã tải xuống",
  };
  els.recordState.innerHTML = `<span></span>${escapeHtml(labels[text] || text)}`;
}

function formatTime(seconds) {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, "0");
  const rest = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${minutes}:${rest}`;
}

function startTimer() {
  state.startedAt = Date.now();
  state.timerInterval = window.setInterval(() => {
    els.timer.textContent = formatTime((Date.now() - state.startedAt) / 1000);
  }, 250);
}

function stopTimer() {
  window.clearInterval(state.timerInterval);
  state.timerInterval = null;
}

function setPipeline(activeStep, doneSteps = []) {
  [...els.pipeline.querySelectorAll("[data-step]")].forEach((item) => {
    const step = item.dataset.step;
    item.classList.toggle("active", step === activeStep);
    item.classList.toggle("done", doneSteps.includes(step));
  });
}

function drawIdleWave() {
  const { width, height } = els.waveform;
  ctx.clearRect(0, 0, width, height);

  const bars = 18;
  const barWidth = 7;
  const gap = 11;
  const totalWidth = bars * barWidth + (bars - 1) * gap;
  const startX = (width - totalWidth) / 2;
  const centerY = height * 0.68;

  ctx.fillStyle = "rgba(15, 118, 110, 0.52)";
  for (let index = 0; index < bars; index += 1) {
    const phase = Date.now() / 580 + index * 0.72;
    const amplitude = 18 + Math.abs(Math.sin(phase)) * 42;
    const x = startX + index * (barWidth + gap);
    const y = centerY - amplitude / 2;
    ctx.beginPath();
    ctx.roundRect(x, y, barWidth, amplitude, 5);
    ctx.fill();
  }

  state.animationFrame = requestAnimationFrame(drawIdleWave);
}

function drawLiveWave() {
  if (!state.analyser) return;
  const buffer = new Uint8Array(state.analyser.frequencyBinCount);
  state.analyser.getByteTimeDomainData(buffer);
  const { width, height } = els.waveform;
  ctx.clearRect(0, 0, width, height);

  const bars = 34;
  const barWidth = 6;
  const gap = 7;
  const totalWidth = bars * barWidth + (bars - 1) * gap;
  const startX = (width - totalWidth) / 2;
  const centerY = height * 0.68;
  const step = Math.floor(buffer.length / bars);

  ctx.fillStyle = "rgba(5, 150, 105, 0.72)";
  for (let index = 0; index < bars; index += 1) {
    const value = buffer[index * step] || 128;
    const normalized = Math.abs(value - 128) / 128;
    const amplitude = 18 + normalized * 118;
    const x = startX + index * (barWidth + gap);
    const y = centerY - amplitude / 2;
    ctx.beginPath();
    ctx.roundRect(x, y, barWidth, amplitude, 5);
    ctx.fill();
  }

  state.animationFrame = requestAnimationFrame(drawLiveWave);
}

function stopWave() {
  if (state.animationFrame) cancelAnimationFrame(state.animationFrame);
  state.animationFrame = null;
}

async function checkHealth() {
  try {
    const response = await fetch("/health");
    if (!response.ok) throw new Error("Health check failed");
    const data = await response.json();
    const ready = data.models.every((model) => model.available);
    setStatus(ready ? "5 models ready" : "Models incomplete", ready ? "ok" : "error");
  } catch (error) {
    setStatus("API offline", "error");
  }
}

function getSupportedMimeType() {
  const options = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/wav"];
  return options.find((type) => MediaRecorder.isTypeSupported(type)) || "";
}

async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      autoGainControl: true,
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
    },
  });
  state.audioChunks = [];
  state.audioBlob = null;
  const mimeType = getSupportedMimeType();
  state.mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);

  state.audioContext = new AudioContext();
  const source = state.audioContext.createMediaStreamSource(stream);
  state.analyser = state.audioContext.createAnalyser();
  state.analyser.fftSize = 2048;
  source.connect(state.analyser);

  state.mediaRecorder.ondataavailable = (event) => {
    if (event.data.size > 0) state.audioChunks.push(event.data);
  };
  state.mediaRecorder.onstop = () => {
    const type = state.mediaRecorder.mimeType || "audio/webm";
    state.audioBlob = new Blob(state.audioChunks, { type });
    if (state.audioUrl) URL.revokeObjectURL(state.audioUrl);
    state.audioUrl = URL.createObjectURL(state.audioBlob);
    els.playback.src = state.audioUrl;
    els.playback.hidden = false;
    els.processBtn.disabled = false;
    stream.getTracks().forEach((track) => track.stop());
    if (state.audioContext) state.audioContext.close();
    stopWave();
    drawIdleWave();
    stopTimer();
    setRecordState("Recorded");
    setPipeline(null, ["record"]);
  };

  stopWave();
  drawLiveWave();
  state.mediaRecorder.start();
  startTimer();
  els.recordBtn.disabled = true;
  els.stopBtn.disabled = false;
  els.processBtn.disabled = true;
  setRecordState("Recording");
  setPipeline("record");
}

function stopRecording() {
  if (state.mediaRecorder && state.mediaRecorder.state !== "inactive") {
    state.mediaRecorder.stop();
  }
  els.recordBtn.disabled = false;
  els.stopBtn.disabled = true;
}

function useImportedFile(file) {
  state.audioBlob = file;
  if (state.audioUrl) URL.revokeObjectURL(state.audioUrl);
  state.audioUrl = URL.createObjectURL(file);
  els.playback.src = state.audioUrl;
  els.playback.hidden = false;
  els.processBtn.disabled = false;
  els.timer.textContent = "00:00";
  setRecordState(file.name);
  setPipeline(null, ["record"]);
}

function extensionForBlob(blob) {
  if (blob.name) return blob.name;
  if (blob.type.includes("mp4")) return "recording.mp4";
  if (blob.type.includes("wav")) return "recording.wav";
  return "recording.webm";
}

async function processAudio() {
  if (!state.audioBlob) return;
  els.body.classList.add("is-busy");
  els.processBtn.disabled = true;
  els.recordBtn.disabled = true;
  setRecordState("Processing");
  setPipeline("upload", ["record"]);

  const formData = new FormData();
  formData.append("file", state.audioBlob, extensionForBlob(state.audioBlob));

  const params = new URLSearchParams({
    language: els.languageSelect.value,
    stt_quality: els.sttQualitySelect.value,
    include_diarization: els.diarizationToggle.checked ? "true" : "false",
    include_summary: els.summaryToggle.checked ? "true" : "false",
  });
  if (els.translateSelect.value) params.set("translate_to", els.translateSelect.value);
  if (els.diarizationToggle.checked && els.speakerCountSelect.value) {
    params.set("num_speakers", els.speakerCountSelect.value);
  }
  if (els.meetingContextInput.value.trim()) {
    params.set("meeting_context", els.meetingContextInput.value.trim());
  }
  params.set("include_llm", els.llmToggle.checked ? "true" : "false");

  try {
    const response = await fetch(`/api/process?${params.toString()}`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Request failed: ${response.status}`);
    }
    const accepted = await response.json();
    if (!accepted.job_id) {
      throw new Error("Server did not return a job id.");
    }

    state.currentJobId = accepted.job_id;
    setRecordState(`Processing ${accepted.job_id.slice(0, 8)}`);
    setPipeline("stt", ["record", "upload"]);

    const result = await pollJobStatus(accepted.job_id);
    if (result.status === "error") {
      throw new Error(`${result.step || "processing"}: ${result.error || "Job failed"}`);
    }

    state.latestResult = normalizeResultForUi(result);
    state.speakerLabels = {};
    renderResult(state.latestResult);
    els.copyBtn.disabled = false;
    if (els.pdfBtn) els.pdfBtn.disabled = false;
    if (els.downloadBtn) els.downloadBtn.disabled = false;
    setRecordState("Complete");
    setPipeline(null, ["record", "upload", "stt", "diarize", "summary"]);
  } catch (error) {
    setRecordState(error.message);
    setPipeline(null, []);
  } finally {
    els.body.classList.remove("is-busy");
    els.processBtn.disabled = false;
    els.recordBtn.disabled = false;
  }
}

async function pollJobStatus(jobId) {
  const startedAt = Date.now();
  while (true) {
    await sleep(2000);
    const response = await fetch(`/api/status/${encodeURIComponent(jobId)}`);
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Status check failed: ${response.status}`);
    }

    const result = await response.json();
    const elapsed = Math.floor((Date.now() - startedAt) / 1000);
    if (result.status !== "processing") return result;

    setRecordState(result.message || `Processing ${formatTime(elapsed)}`);
    if (elapsed > 5) setPipeline("diarize", ["record", "upload", "stt"]);
    if (elapsed > 20) setPipeline("summary", ["record", "upload", "stt", "diarize"]);
    if (result.step === "speech_to_text") setPipeline("stt", ["record", "upload", "diarize"]);
    if (result.step === "llm_correction") setPipeline("summary", ["record", "upload", "diarize", "stt"]);
    if (result.step === "summary" || result.step === "llm_refinement") {
      setPipeline("summary", ["record", "upload", "diarize", "stt"]);
    }
  }
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function normalizeResultForUi(result) {
  if (result.transcript || result.diarization?.segments) return result;

  const transcriptSegments = (result.original_transcript || []).map((segment) => ({
    id: segment.id,
    start: Number(segment.start || 0),
    end: Number(segment.end || 0),
    speaker: segment.speaker || null,
    text: segment.text || "",
  }));
  const diarizationSegments = (result.diarization || []).map((segment) => ({
    start: Number(segment.start || 0),
    end: Number(segment.end || 0),
    speaker: segment.speaker || "",
  }));
  return {
    ...result,
    transcript: {
      segments: transcriptSegments,
      text: transcriptSegments.map((segment) => segment.text).join(" "),
    },
    diarization: {
      segments: diarizationSegments,
    },
    meeting_minutes: result.corrected_transcript || result.merged_transcript || "",
    warnings: result.job_id ? [`Job ${result.job_id}`] : [],
  };
}

function renderResult(result) {
  const warnings = [...(result.warnings || [])];
  if (result.original_transcript?.text) {
    warnings.push("Transcript ASR gốc có trong phản hồi API để đối chiếu khi cần.");
  }
  renderWarnings(warnings);
  renderSummary(result);
  els.translationOutput.innerHTML = renderTranslationAndActions(result);
  renderSpeakerLabelControls(result);
  renderTranscript(result.transcript?.segments || []);
  renderSpeakers(result.diarization?.segments || []);
}

function renderSummary(result) {
  const summary =
    result.meeting_minutes ||
    result.llm_summary ||
    result.translated_summary ||
    result.summary;

  if (!summary) {
    els.summaryOutput.innerHTML = compactEmptyState("Chưa có bản tóm tắt. Hãy ghi âm hoặc tải file để xử lý.");
    return;
  }

  els.summaryOutput.textContent = labelText(summary);
}

function renderTranslationAndActions(result) {
  const parts = [];
  const translation = result.translated_transcript || result.translated_text;
  if (translation) {
    parts.push(`<div>${escapeHtml(labelText(translation))}</div>`);
  }
  if (result.action_items?.length) {
    const rows = result.action_items
      .map((item) => {
        const assignee = item.assignee ? labelText(item.assignee) : null;
        const meta = [assignee, item.deadline].filter(Boolean).join(" · ");
        return `<div class="speaker-row"><span>${escapeHtml(labelText(item.task))}</span><span class="segment-time">${escapeHtml(meta || "chưa có người phụ trách/thời hạn")}</span></div>`;
      })
      .join("");
    parts.push(`<div class="action-list">${rows}</div>`);
  }
  if (result.decisions?.length) {
    parts.push(`<div>${result.decisions.map((item) => `Quyết định: ${escapeHtml(labelText(item))}`).join("<br>")}</div>`);
  }
  return parts.join("") || compactEmptyState("Chưa có bản dịch.");
}

function renderWarnings(warnings) {
  if (!warnings.length) {
    els.warningOutput.hidden = true;
    els.warningOutput.textContent = "";
    return;
  }
  els.warningOutput.hidden = false;
  els.warningOutput.textContent = warnings.join(" · ");
}

function renderTranscript(segments) {
  if (!segments.length) {
    els.transcriptOutput.innerHTML = largeTranscriptEmptyState();
    return;
  }
  els.transcriptOutput.innerHTML = segments
    .map(
      (segment) => `
      <div class="segment">
        <div>
          <div class="segment-time">${segment.start.toFixed(1)}-${segment.end.toFixed(1)}s</div>
          <div class="speaker-chip">${escapeHtml(displaySpeaker(segment.speaker))}</div>
        </div>
        <div>${escapeHtml(segment.text)}</div>
      </div>
    `,
    )
    .join("");
}

function renderSpeakers(segments) {
  if (!segments.length) {
    els.speakerOutput.innerHTML = defaultSpeakerChips();
    return;
  }
  els.speakerOutput.innerHTML = segments
    .map(
      (segment) => `
      <div class="speaker-row">
        <span class="speaker-chip">${escapeHtml(displaySpeaker(segment.speaker))}</span>
        <span class="segment-time">${segment.start.toFixed(1)}-${segment.end.toFixed(1)}s</span>
      </div>
    `,
    )
    .join("");
}

function compactEmptyState(text) {
  return `<div class="empty-state compact">${escapeHtml(text)}</div>`;
}

function largeTranscriptEmptyState() {
  return `
    <div class="empty-state large">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
        <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
        <path d="M12 19v3"></path>
      </svg>
      <p>Chưa có transcript. Hãy ghi âm hoặc tải file để bắt đầu.</p>
    </div>
  `;
}

function defaultSpeakerChips() {
  return `
    <div class="speaker-chip-list">
      <span>Speaker 1</span>
      <span>Speaker 2</span>
      <span>Speaker 3</span>
    </div>
  `;
}

function renderSpeakerLabelControls(result) {
  const speakers = collectSpeakers(result);
  if (!speakers.length) {
    els.speakerLabelControls.hidden = true;
    els.speakerLabelControls.innerHTML = "";
    return;
  }

  els.speakerLabelControls.hidden = false;
  els.speakerLabelControls.innerHTML = speakers
    .map(
      (speaker) => `
      <label class="speaker-label-row">
        <span class="speaker-chip">${escapeHtml(speaker)}</span>
        <input
          type="text"
          data-speaker="${escapeHtml(speaker)}"
          value="${escapeHtml(state.speakerLabels[speaker] || "")}"
          placeholder="Nhập tên người nói"
          aria-label="Gán tên cho ${escapeHtml(speaker)}"
        />
      </label>
    `,
    )
    .join("");

  [...els.speakerLabelControls.querySelectorAll("input")].forEach((input) => {
    input.addEventListener("input", (event) => {
      const speaker = event.target.dataset.speaker;
      const label = event.target.value.trim();
      if (label) state.speakerLabels[speaker] = label;
      else delete state.speakerLabels[speaker];
      renderSummary(state.latestResult || {});
      els.translationOutput.innerHTML = renderTranslationAndActions(state.latestResult || {});
      renderTranscript(state.latestResult?.transcript?.segments || []);
      renderSpeakers(state.latestResult?.diarization?.segments || []);
    });
  });
}

function collectSpeakers(result) {
  const speakers = new Set();
  result.diarization?.segments?.forEach((segment) => {
    if (segment.speaker) speakers.add(segment.speaker);
  });
  result.transcript?.segments?.forEach((segment) => {
    if (segment.speaker) speakers.add(segment.speaker);
  });
  return [...speakers].sort();
}

function displaySpeaker(speaker) {
  if (!speaker) return "SPEAKER";
  return state.speakerLabels[speaker] || speaker;
}

function labelText(text) {
  let labeledText = String(text || "");
  Object.entries(state.speakerLabels).forEach(([speaker, label]) => {
    if (!label) return;
    labeledText = labeledText.replace(new RegExp(escapeRegExp(speaker), "g"), label);
  });
  return labeledText;
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return map[char];
  });
}

async function copyResult() {
  if (!state.latestResult) return;
  await navigator.clipboard.writeText(composeResultText());
  setRecordState("Copied");
}

function composeResultText() {
  const transcript = state.latestResult.transcript?.segments
    ?.map((segment) => `${displaySpeaker(segment.speaker)} [${segment.start}-${segment.end}s]: ${segment.text}`)
    .join("\n");
  const summary =
    state.latestResult.meeting_minutes ||
    state.latestResult.llm_summary ||
    state.latestResult.translated_summary ||
    state.latestResult.summary ||
    "";
  const text = [
    "TÓM TẮT",
    labelText(summary),
    "",
    "BẢN DỊCH",
    labelText(state.latestResult.translated_transcript || state.latestResult.translated_text || ""),
    "",
    "TRANSCRIPT",
    transcript || "",
  ].join("\n");
  return text;
}

function exportPdf() {
  if (!state.latestResult) return;
  window.print();
}

function downloadResult() {
  if (!state.latestResult) return;
  const blob = new Blob([composeResultText()], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `bien-ban-cuoc-hop-${new Date().toISOString().slice(0, 10)}.txt`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  setRecordState("Downloaded");
}

els.recordBtn.addEventListener("click", () => {
  startRecording().catch((error) => setRecordState(error.message));
});
els.stopBtn.addEventListener("click", stopRecording);
els.processBtn.addEventListener("click", processAudio);
els.fileInput.addEventListener("change", (event) => {
  const [file] = event.target.files;
  if (file) useImportedFile(file);
});
els.copyBtn.addEventListener("click", copyResult);
els.pdfBtn?.addEventListener("click", exportPdf);
els.downloadBtn?.addEventListener("click", downloadResult);

drawIdleWave();
checkHealth();
