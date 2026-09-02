const ROLE_NAMES = ["A", "B", "C", "D", "E", "F"];
const SAMPLE_SRT = `1
00:00:01,000 --> 00:00:03,200
林晓：你确定今晚还要进去吗？

2
00:00:03,500 --> 00:00:05,200
周远：门已经开了，现在回头才奇怪。

3
00:00:05,900 --> 00:00:07,300
别吵，我听见里面有人。

4
00:00:08,000 --> 00:00:10,500
林晓：那不是人声，是广播。

5
00:00:11,000 --> 00:00:13,200
周远：广播不会叫我的名字。

6
00:00:14,000 --> 00:00:16,000
管理员：访客请立即离开三号楼。`;

const state = {
  cues: [],
  speakers: [],
  voices: [],
  serverVoices: [],
  useServerVoices: false,
  roleVoices: {},
  playing: false,
};

const els = {
  fileInput: document.querySelector("#fileInput"),
  dropZone: document.querySelector("#dropZone"),
  srtInput: document.querySelector("#srtInput"),
  analyzeBtn: document.querySelector("#analyzeBtn"),
  sampleBtn: document.querySelector("#sampleBtn"),
  languageSelect: document.querySelector("#languageSelect"),
  speakerCount: document.querySelector("#speakerCount"),
  roleCount: document.querySelector("#roleCount"),
  speakerCards: document.querySelector("#speakerCards"),
  subtitleBody: document.querySelector("#subtitleBody"),
  lineCount: document.querySelector("#lineCount"),
  detectedCount: document.querySelector("#detectedCount"),
  voiceCount: document.querySelector("#voiceCount"),
  selectAll: document.querySelector("#selectAll"),
  playAllBtn: document.querySelector("#playAllBtn"),
  exportAudioBtn: document.querySelector("#exportAudioBtn"),
  previewRolesBtn: document.querySelector("#previewRolesBtn"),
  exportSrtBtn: document.querySelector("#exportSrtBtn"),
  exportJsonBtn: document.querySelector("#exportJsonBtn"),
};

function parseSrt(input) {
  const normalized = input.replace(/\r/g, "").trim();
  if (!normalized) return [];

  return normalized
    .split(/\n{2,}/)
    .map((block, blockIndex) => {
      const lines = block.split("\n").filter(Boolean);
      const maybeIndex = /^\d+$/.test(lines[0]?.trim()) ? lines.shift() : String(blockIndex + 1);
      const timeLineIndex = lines.findIndex((line) => line.includes("-->"));
      if (timeLineIndex === -1) return null;

      const time = lines[timeLineIndex].trim();
      const text = lines.slice(timeLineIndex + 1).join("\n").trim();
      const extracted = extractSpeakerLabel(text);

      return {
        id: crypto.randomUUID(),
        index: Number(maybeIndex) || blockIndex + 1,
        time,
        originalText: text,
        text: extracted.text,
        explicitSpeaker: extracted.speaker,
        speaker: "",
        role: "",
        selected: true,
      };
    })
    .filter(Boolean);
}

function extractSpeakerLabel(text) {
  const trimmed = text.trim();
  const bracket = trimmed.match(/^\[(?:speaker|spk|角色|人物)\s*([A-Za-z0-9_-]+)\]\s*/i);
  if (bracket) {
    return {
      speaker: `Speaker ${bracket[1]}`,
      text: trimmed.slice(bracket[0].length).trim(),
    };
  }

  const named = trimmed.match(/^([\p{Script=Han}A-Za-z][\p{Script=Han}A-Za-z0-9 _-]{0,12})[:：]\s*(.+)$/u);
  if (named && !looksLikeTimestamp(named[1])) {
    return { speaker: named[1].trim(), text: named[2].trim() };
  }

  return { speaker: "", text: trimmed };
}

function looksLikeTimestamp(value) {
  return /\d{1,2}:\d{2}/.test(value);
}

function inferSpeakerCount(cues) {
  const explicit = new Set(cues.map((cue) => cue.explicitSpeaker).filter(Boolean));
  if (explicit.size) return Math.min(8, explicit.size);
  const selected = els.speakerCount.value;
  if (selected !== "auto") return Number(selected);

  if (cues.length < 8) return 2;
  if (cues.length < 22) return 3;
  if (cues.some((cue) => /[?!？！]|别|等等|为什么|who|why|wait/i.test(cue.text))) return 4;
  return 3;
}

function textFeatures(text) {
  const clean = text.replace(/[“”"'\-—]/g, "");
  return {
    len: clean.length,
    question: /[?？]/.test(clean) ? 1 : 0,
    exclaim: /[!！]/.test(clean) ? 1 : 0,
    polite: /请|谢谢|麻烦|please|thanks/i.test(clean) ? 1 : 0,
    command: /别|快|走|停|listen|go|stop|wait/i.test(clean) ? 1 : 0,
  };
}

function assignSpeakers(cues) {
  const explicitNames = [...new Set(cues.map((cue) => cue.explicitSpeaker).filter(Boolean))];
  const targetCount = Number(els.speakerCount.value === "auto" ? inferSpeakerCount(cues) : els.speakerCount.value);
  const names =
    explicitNames.length > 0
      ? explicitNames
      : Array.from({ length: targetCount }, (_, index) => `人物 ${index + 1}`);

  const profiles = names.map(() => ({ len: 0, question: 0, exclaim: 0, polite: 0, command: 0, count: 0 }));
  let lastSpeakerIndex = -1;

  cues.forEach((cue, index) => {
    if (cue.explicitSpeaker) {
      cue.speaker = cue.explicitSpeaker;
    } else {
      const features = textFeatures(cue.text);
      let bestIndex = 0;
      let bestScore = -Infinity;

      names.forEach((_, speakerIndex) => {
        const profile = profiles[speakerIndex];
        const turnBonus = speakerIndex === (lastSpeakerIndex + 1) % names.length ? 3 : 0;
        const repeatPenalty = speakerIndex === lastSpeakerIndex ? -2 : 0;
        const lengthFit = profile.count ? -Math.abs(features.len - profile.len / profile.count) / 18 : 0;
        const styleFit =
          profile.count === 0
            ? 0
            : Math.abs(features.question - profile.question / profile.count) +
              Math.abs(features.exclaim - profile.exclaim / profile.count) +
              Math.abs(features.polite - profile.polite / profile.count) +
              Math.abs(features.command - profile.command / profile.count);
        const score = turnBonus + repeatPenalty + lengthFit - styleFit + ((index + speakerIndex) % 3) * 0.05;
        if (score > bestScore) {
          bestScore = score;
          bestIndex = speakerIndex;
        }
      });

      cue.speaker = names[bestIndex];
    }

    const profileIndex = Math.max(0, names.indexOf(cue.speaker));
    const features = textFeatures(cue.text);
    profiles[profileIndex].len += features.len;
    profiles[profileIndex].question += features.question;
    profiles[profileIndex].exclaim += features.exclaim;
    profiles[profileIndex].polite += features.polite;
    profiles[profileIndex].command += features.command;
    profiles[profileIndex].count += 1;
    lastSpeakerIndex = profileIndex;
  });

  state.speakers = names.map((name, index) => ({
    name,
    role: ROLE_NAMES[index % Number(els.roleCount.value)],
  }));
  cues.forEach((cue) => {
    cue.role = speakerToRole(cue.speaker);
  });
}

function speakerToRole(speakerName) {
  return state.speakers.find((speaker) => speaker.name === speakerName)?.role || "A";
}

function roleOptions(selected) {
  return ROLE_NAMES.slice(0, Number(els.roleCount.value))
    .map((role) => `<option value="${role}" ${role === selected ? "selected" : ""}>角色 ${role}</option>`)
    .join("");
}

function speakerOptions(selected) {
  return state.speakers
    .map((speaker) => `<option value="${escapeHtml(speaker.name)}" ${speaker.name === selected ? "selected" : ""}>${escapeHtml(speaker.name)}</option>`)
    .join("");
}

function voiceOptions(selectedVoiceURI = "") {
  const lang = els.languageSelect.value;
  const allVoices = currentVoices();
  const voices = allVoices.filter((voice) => !lang || voice.lang.toLowerCase().startsWith(lang));
  const usable = voices.length ? voices : allVoices;
  if (!usable.length) return `<option value="">浏览器暂无可用系统声音</option>`;
  return usable
    .map((voice) => {
      const label = `${voice.name} (${voice.lang || "system"})${voice.localService || state.useServerVoices ? " 本地" : ""}`;
      return `<option value="${escapeHtml(voice.voiceURI)}" ${voice.voiceURI === selectedVoiceURI ? "selected" : ""}>${escapeHtml(label)}</option>`;
    })
    .join("");
}

function currentVoices() {
  return state.useServerVoices ? state.serverVoices : state.voices;
}

function render() {
  els.lineCount.textContent = state.cues.length;
  els.detectedCount.textContent = state.speakers.length;
  els.voiceCount.textContent = currentVoices().length;
  els.exportAudioBtn.disabled = !state.useServerVoices || !state.cues.length;
  els.exportAudioBtn.title = state.useServerVoices ? "导出选中字幕逐句 WAV" : "启动本地服务后可导出 WAV";
  renderSpeakerCards();
  renderTable();
}

function renderSpeakerCards() {
  if (!state.speakers.length) {
    els.speakerCards.innerHTML = "";
    return;
  }

  els.speakerCards.innerHTML = state.speakers
    .map((speaker) => {
      const count = state.cues.filter((cue) => cue.speaker === speaker.name).length;
      const voiceUri = state.roleVoices[speaker.role] || "";
      return `<article class="speaker-card">
        <header>
          <span class="speaker-name">${escapeHtml(speaker.name)}</span>
          <span class="badge">${count} 句</span>
        </header>
        <div class="card-grid">
          <label for="role-${slug(speaker.name)}">合并到</label>
          <select id="role-${slug(speaker.name)}" data-speaker-role="${escapeHtml(speaker.name)}">${roleOptions(speaker.role)}</select>
          <label for="voice-${slug(speaker.name)}">声音</label>
          <select id="voice-${slug(speaker.name)}" data-role-voice="${speaker.role}">${voiceOptions(voiceUri)}</select>
        </div>
      </article>`;
    })
    .join("");
}

function renderTable() {
  if (!state.cues.length) {
    els.subtitleBody.innerHTML = `<tr class="empty-row"><td colspan="7">导入或粘贴 SRT 后点击“智能识别”。</td></tr>`;
    return;
  }

  els.subtitleBody.innerHTML = state.cues
    .map(
      (cue, rowIndex) => `<tr>
        <td><input type="checkbox" data-select-row="${cue.id}" ${cue.selected ? "checked" : ""} /></td>
        <td>${rowIndex + 1}</td>
        <td>${escapeHtml(cue.time)}</td>
        <td><select class="compact-select" data-row-speaker="${cue.id}">${speakerOptions(cue.speaker)}</select></td>
        <td><select class="compact-select" data-row-role="${cue.id}">${roleOptions(cue.role)}</select></td>
        <td><textarea class="row-text" data-row-text="${cue.id}">${escapeHtml(cue.text)}</textarea></td>
        <td><button class="ghost play-line" data-play-row="${cue.id}" type="button" aria-label="试听第 ${rowIndex + 1} 行">▶</button></td>
      </tr>`
    )
    .join("");
}

function analyze() {
  const cues = parseSrt(els.srtInput.value);
  if (!cues.length) {
    alert("没有识别到有效 SRT，请检查时间轴格式。");
    return;
  }
  state.cues = cues;
  assignSpeakers(state.cues);
  assignDefaultVoices();
  render();
}

function assignDefaultVoices() {
  const lang = els.languageSelect.value;
  const allVoices = currentVoices();
  const voices = allVoices.filter((voice) => !lang || voice.lang.toLowerCase().startsWith(lang));
  const usable = voices.length ? voices : allVoices;
  ROLE_NAMES.slice(0, Number(els.roleCount.value)).forEach((role, index) => {
    if (!state.roleVoices[role]) {
      state.roleVoices[role] = usable[index % Math.max(1, usable.length)]?.voiceURI || "";
    }
  });
}

function loadVoices() {
  state.voices = speechSynthesis.getVoices().sort((a, b) => a.lang.localeCompare(b.lang) || a.name.localeCompare(b.name));
  assignDefaultVoices();
  render();
}

async function loadServerVoices() {
  try {
    const response = await fetch("/api/voices", { cache: "no-store" });
    if (!response.ok) return;
    const voices = await response.json();
    state.serverVoices = voices.map((voice) => ({
      name: voice.name,
      voiceURI: voice.id,
      lang: voice.lang || "",
      localService: true,
    }));
    state.useServerVoices = state.serverVoices.length > 0;
    state.roleVoices = {};
    assignDefaultVoices();
    render();
  } catch {
    state.useServerVoices = false;
  }
}

function speak(text, role = "A") {
  if (state.useServerVoices) {
    return speakWithServer(text, role);
  }

  if (!("speechSynthesis" in window)) {
    alert("当前浏览器不支持系统语音朗读。建议用 Edge 或 Chrome 打开。");
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    const voiceUri = state.roleVoices[role];
    const voice = state.voices.find((item) => item.voiceURI === voiceUri);
    if (voice) utterance.voice = voice;
    utterance.rate = 1;
    utterance.pitch = 1;
    utterance.onend = resolve;
    utterance.onerror = resolve;
    speechSynthesis.speak(utterance);
  });
}

async function speakWithServer(text, role) {
  const response = await fetch("/api/speak", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, voice: state.roleVoices[role] || "" }),
  });
  if (!response.ok) {
    alert("本地系统声音生成失败，请换一个声音再试。");
    return;
  }
  const blob = await response.blob();
  const audio = new Audio(URL.createObjectURL(blob));
  await audio.play();
  await new Promise((resolve) => {
    audio.onended = resolve;
    audio.onerror = resolve;
  });
}

async function playSelected() {
  if (state.playing) {
    state.playing = false;
    speechSynthesis.cancel();
    els.playAllBtn.textContent = "播放选中";
    return;
  }

  state.playing = true;
  els.playAllBtn.textContent = "停止";
  for (const cue of state.cues.filter((item) => item.selected)) {
    if (!state.playing) break;
    await speak(cue.text, cue.role);
    await wait(120);
  }
  state.playing = false;
  els.playAllBtn.textContent = "播放选中";
}

async function previewRoles() {
  const roles = ROLE_NAMES.slice(0, Number(els.roleCount.value));
  for (const role of roles) {
    await speak(`这是角色 ${role} 的系统声音。`, role);
    await wait(120);
  }
}

function exportTaggedSrt() {
  const content = state.cues
    .map((cue, index) => `${index + 1}\n${cue.time}\n[speaker${ROLE_NAMES.indexOf(cue.role) + 1}] ${cue.text}`)
    .join("\n\n");
  download("smart-cast.srt", content, "text/plain;charset=utf-8");
}

function exportConfig() {
  const payload = {
    generatedAt: new Date().toISOString(),
    roles: ROLE_NAMES.slice(0, Number(els.roleCount.value)).map((role) => ({
      role,
      voiceURI: state.roleVoices[role] || "",
      voiceName: state.voices.find((voice) => voice.voiceURI === state.roleVoices[role])?.name || "",
    })),
    speakers: state.speakers,
    cues: state.cues.map(({ id, ...cue }) => cue),
  };
  download("smart-cast-config.json", JSON.stringify(payload, null, 2), "application/json;charset=utf-8");
}

async function exportAudioZip() {
  if (!state.useServerVoices) {
    alert("请用 python server.py 启动本地服务后再导出 WAV 包。");
    return;
  }

  const selectedCues = state.cues.filter((cue) => cue.selected);
  if (!selectedCues.length) {
    alert("没有选中的字幕行。");
    return;
  }

  els.exportAudioBtn.disabled = true;
  els.exportAudioBtn.textContent = "生成中...";
  try {
    const response = await fetch("/api/export-wav", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        roles: Object.fromEntries(
          ROLE_NAMES.map((role) => [role, state.roleVoices[role] || ""]).filter(([, voice]) => voice)
        ),
        cues: selectedCues.map((cue, index) => ({
          index: index + 1,
          time: cue.time,
          text: cue.text,
          role: cue.role,
          speaker: cue.speaker,
        })),
      }),
    });
    if (!response.ok) throw new Error(await response.text());
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "smart-cast-wav.zip";
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    alert(`导出 WAV 失败：${error.message || "未知错误"}`);
  } finally {
    els.exportAudioBtn.disabled = false;
    els.exportAudioBtn.textContent = "导出 WAV 包";
  }
}

function download(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function slug(value) {
  return String(value).replace(/[^\w-]+/g, "-");
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

els.sampleBtn.addEventListener("click", () => {
  els.srtInput.value = SAMPLE_SRT;
  analyze();
});

els.analyzeBtn.addEventListener("click", analyze);
els.playAllBtn.addEventListener("click", playSelected);
els.exportAudioBtn.addEventListener("click", exportAudioZip);
els.previewRolesBtn.addEventListener("click", previewRoles);
els.exportSrtBtn.addEventListener("click", exportTaggedSrt);
els.exportJsonBtn.addEventListener("click", exportConfig);

els.fileInput.addEventListener("change", async (event) => {
  const [file] = event.target.files;
  if (!file) return;
  els.srtInput.value = await file.text();
  analyze();
});

["dragenter", "dragover"].forEach((eventName) => {
  els.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    els.dropZone.classList.add("dragging");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  els.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    els.dropZone.classList.remove("dragging");
  });
});

els.dropZone.addEventListener("drop", async (event) => {
  const [file] = event.dataTransfer.files;
  if (!file) return;
  els.srtInput.value = await file.text();
  analyze();
});

els.languageSelect.addEventListener("change", () => {
  state.roleVoices = {};
  assignDefaultVoices();
  render();
});

els.roleCount.addEventListener("change", () => {
  state.speakers.forEach((speaker, index) => {
    speaker.role = ROLE_NAMES[index % Number(els.roleCount.value)];
  });
  state.cues.forEach((cue) => {
    cue.role = speakerToRole(cue.speaker);
  });
  state.roleVoices = {};
  assignDefaultVoices();
  render();
});

els.speakerCards.addEventListener("change", (event) => {
  const roleTarget = event.target.closest("[data-speaker-role]");
  const voiceTarget = event.target.closest("[data-role-voice]");

  if (roleTarget) {
    const speakerName = roleTarget.dataset.speakerRole;
    const speaker = state.speakers.find((item) => item.name === speakerName);
    if (speaker) {
      speaker.role = roleTarget.value;
      state.cues.forEach((cue) => {
        if (cue.speaker === speakerName) cue.role = roleTarget.value;
      });
      render();
    }
  }

  if (voiceTarget) {
    state.roleVoices[voiceTarget.dataset.roleVoice] = voiceTarget.value;
  }
});

els.subtitleBody.addEventListener("change", (event) => {
  const selectRow = event.target.closest("[data-select-row]");
  const rowSpeaker = event.target.closest("[data-row-speaker]");
  const rowRole = event.target.closest("[data-row-role]");
  if (selectRow) state.cues.find((cue) => cue.id === selectRow.dataset.selectRow).selected = selectRow.checked;
  if (rowSpeaker) {
    const cue = state.cues.find((item) => item.id === rowSpeaker.dataset.rowSpeaker);
    cue.speaker = rowSpeaker.value;
    cue.role = speakerToRole(cue.speaker);
    render();
  }
  if (rowRole) state.cues.find((cue) => cue.id === rowRole.dataset.rowRole).role = rowRole.value;
});

els.subtitleBody.addEventListener("input", (event) => {
  const rowText = event.target.closest("[data-row-text]");
  if (rowText) state.cues.find((cue) => cue.id === rowText.dataset.rowText).text = rowText.value;
});

els.subtitleBody.addEventListener("click", (event) => {
  const playRow = event.target.closest("[data-play-row]");
  if (!playRow) return;
  const cue = state.cues.find((item) => item.id === playRow.dataset.playRow);
  speak(cue.text, cue.role);
});

els.selectAll.addEventListener("change", () => {
  state.cues.forEach((cue) => {
    cue.selected = els.selectAll.checked;
  });
  render();
});

if ("speechSynthesis" in window) {
  speechSynthesis.onvoiceschanged = loadVoices;
  loadVoices();
} else {
  render();
}

loadServerVoices();
