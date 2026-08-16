const prefs = {
  speak: localStorage.getItem("atlas.speakReplies") === "true",
  autoSend: localStorage.getItem("atlas.autoSend") !== "false",
  twoWay: localStorage.getItem("atlas.twoWay") === "true",
  silenceMs: Number(localStorage.getItem("atlas.silenceMs") || 700),
  rate: Number(localStorage.getItem("atlas.speakRate") || 1.05),
};

const thinkStages = [
  "searching Qdrant for nearby email vectors…",
  "ranking retrieved chunks…",
  "generating an answer from sources…",
];

let config = { tts: { provider: "none" }, stt: { provider: "whisper", vad: true } };
let listening = false;
let audioCtx = null;
let workletNode = null;
let recognition = null;
let pcmChunks = [];
let pcmRate = 16000;
let speakAudio = null;
let cancelled = false;
let speakGen = 0;
let holdTalk = false;
let pressTimer = null;
let vuRaf = 0;

const messagesEl = document.getElementById("messages");
const emptyEl = document.getElementById("empty");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send-btn");
const micBtn = document.getElementById("mic-btn");
const statusEl = document.getElementById("mic-status");
const lamp = document.getElementById("voice-lamp");
const vu = document.getElementById("vu");
const twoWay = document.getElementById("two-way");
const speakReplies = document.getElementById("speak-replies");
const autoSend = document.getElementById("auto-send");
const silenceMs = document.getElementById("silence-ms");
const speakRate = document.getElementById("speak-rate");

document.getElementById("nav").innerHTML = nav("chat");
document.getElementById("hero").innerHTML = terminal("internal assistant online · grounded on company email");

speakReplies.checked = prefs.speak;
autoSend.checked = prefs.autoSend;
twoWay.checked = prefs.twoWay;
silenceMs.value = String(prefs.silenceMs);
speakRate.value = String(prefs.rate);
syncLabels();

function persist() {
  localStorage.setItem("atlas.speakReplies", String(prefs.speak));
  localStorage.setItem("atlas.autoSend", String(prefs.autoSend));
  localStorage.setItem("atlas.twoWay", String(prefs.twoWay));
  localStorage.setItem("atlas.silenceMs", String(prefs.silenceMs));
  localStorage.setItem("atlas.speakRate", String(prefs.rate));
}

function syncLabels() {
  document.getElementById("silence-label").textContent = `${prefs.silenceMs} ms`;
  document.getElementById("rate-label").textContent = `${Number(prefs.rate).toFixed(2)}×`;
}

function setStatus(text) {
  statusEl.textContent = text || "";
}

function setLamp(mode, label) {
  lamp.dataset.mode = mode;
  lamp.textContent = label;
}

function hideEmpty() {
  if (emptyEl) emptyEl.style.display = "none";
}

twoWay.addEventListener("change", () => {
  prefs.twoWay = twoWay.checked;
  if (prefs.twoWay) {
    prefs.speak = true;
    prefs.autoSend = true;
    speakReplies.checked = true;
    autoSend.checked = true;
  }
  persist();
});
speakReplies.addEventListener("change", () => {
  prefs.speak = speakReplies.checked;
  persist();
});
autoSend.addEventListener("change", () => {
  prefs.autoSend = autoSend.checked;
  persist();
});
silenceMs.addEventListener("input", () => {
  prefs.silenceMs = Number(silenceMs.value) || 700;
  syncLabels();
  persist();
});
speakRate.addEventListener("input", () => {
  prefs.rate = Number(speakRate.value) || 1.05;
  syncLabels();
  persist();
});

function appendMessage(text, role, citations = []) {
  hideEmpty();
  const node = document.createElement("div");
  node.className = `msg ${role}`;
  const tag = document.createElement("div");
  tag.className = "msg-tag";
  tag.textContent = role === "user" ? "operator" : role === "think" ? "atlas · thinking" : "atlas";
  const body = document.createElement("div");
  body.className = "msg-body";
  body.appendChild(document.createTextNode(text));
  node.appendChild(tag);
  node.appendChild(body);
  if (role === "bot" && text) {
    const replay = document.createElement("button");
    replay.className = "ghost-btn replay";
    replay.type = "button";
    replay.textContent = "Speak";
    replay.addEventListener("click", () => speak(text, { loop: false }));
    node.appendChild(replay);
  }
  if (citations.length) {
    const box = document.createElement("div");
    box.className = "sources";
    citations.forEach((item) => {
      const link = document.createElement("a");
      const id = item.message_id || item.metadata?.message_id;
      link.href = id ? `/qdrant.html?id=${encodeURIComponent(id)}` : "/qdrant.html";
      link.textContent = item.subject || "source";
      box.appendChild(link);
    });
    node.appendChild(box);
  }
  messagesEl.appendChild(node);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return node;
}

function autosize() {
  inputEl.style.height = "auto";
  inputEl.style.height = `${Math.min(inputEl.scrollHeight, 160)}px`;
}

async function sendMessage(text) {
  const message = (text ?? inputEl.value).trim();
  if (!message) return;
  cancelled = false;
  inputEl.value = "";
  autosize();
  appendMessage(message, "user");
  sendBtn.disabled = true;
  const think = appendMessage(thinkStages[0], "think");
  think.querySelector(".msg-body").innerHTML =
    `<div class="think-row"><span class="spinner"></span><span id="think-text">${thinkStages[0]}</span></div>`;
  let stage = 0;
  const timer = setInterval(() => {
    stage = Math.min(stage + 1, thinkStages.length - 1);
    const label = document.getElementById("think-text");
    if (label) label.textContent = thinkStages[stage];
  }, 1800);
  try {
    const data = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    think.remove();
    appendMessage(data.answer, "bot", data.citations || []);
    if (prefs.speak || prefs.twoWay) await speak(data.answer, { loop: prefs.twoWay });
  } catch (error) {
    think.remove();
    appendMessage(`Error: ${error.message}`, "bot");
  } finally {
    clearInterval(timer);
    sendBtn.disabled = false;
    inputEl.focus();
  }
}

const GOOGLE_VOICES = [
  ["en-AU-Chirp3-HD-Kore", "AU Chirp 3 HD · Kore"],
  ["en-AU-Chirp3-HD-Aoede", "AU Chirp 3 HD · Aoede"],
  ["en-AU-Chirp3-HD-Charon", "AU Chirp 3 HD · Charon"],
  ["en-AU-Chirp3-HD-Fenrir", "AU Chirp 3 HD · Fenrir"],
  ["en-US-Chirp3-HD-Kore", "US Chirp 3 HD · Kore"],
  ["en-US-Chirp3-HD-Charon", "US Chirp 3 HD · Charon"],
  ["en-US-Studio-O", "US Studio · O"],
  ["en-AU-Neural2-C", "AU Neural2 · C"],
  ["en-US-Neural2-J", "US Neural2 · J"],
];

const voiceSelect = document.getElementById("voice-select");
const stopAudioBtn = document.getElementById("stop-audio");

prefs.voice = localStorage.getItem("atlas.voice") || "";

function setSpeaking(on) {
  stopAudioBtn.classList.toggle("hot", Boolean(on));
  document.getElementById("stop-btn").classList.toggle("hot", Boolean(on));
}

function stopSpeaking() {
  speakGen += 1;
  if (speakAudio) {
    const audio = speakAudio;
    speakAudio = null;
    audio.onended = null;
    audio.onerror = null;
    try {
      audio.pause();
      audio.src = "";
    } catch (_error) {
      /* already stopped */
    }
  }
  if (window.speechSynthesis) window.speechSynthesis.cancel();
  setSpeaking(false);
  if (!listening) setLamp("idle", "idle");
}

function haltAudio() {
  cancelled = true;
  stopSpeaking();
  setStatus("");
}

async function speak(text, { loop = false } = {}) {
  stopSpeaking();
  cancelled = false;
  const gen = speakGen;
  const spoken = String(text || "")
    .replace(/\[[0-9]+\]/g, "")
    .trim();
  if (!spoken) return;
  setLamp("speak", "speaking");
  setSpeaking(true);
  try {
    if (config.tts?.provider === "google") {
      try {
        const response = await fetch("/api/voice/synthesize", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: spoken.slice(0, 4000),
            speaking_rate: prefs.rate,
            voice: prefs.voice || undefined,
          }),
        });
        if (!response.ok) throw new Error("Google TTS unavailable");
        if (gen !== speakGen) return;
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        await new Promise((resolve) => {
          if (gen !== speakGen) {
            URL.revokeObjectURL(url);
            resolve();
            return;
          }
          speakAudio = new Audio(url);
          speakAudio.onended = resolve;
          speakAudio.onerror = resolve;
          speakAudio.play().catch(resolve);
        });
        URL.revokeObjectURL(url);
      } catch (error) {
        if (gen === speakGen) {
          setStatus(`${error.message}. Browser voice standing in.`);
          await speakBrowser(spoken, gen);
        }
      }
    } else {
      await speakBrowser(spoken, gen);
    }
  } finally {
    if (gen === speakGen) {
      setSpeaking(false);
      if (!listening) setLamp("idle", "idle");
    }
  }
  if (loop && prefs.twoWay && !cancelled && gen === speakGen) await startListening();
}

function speakBrowser(text, gen = speakGen) {
  if (!window.speechSynthesis) return Promise.resolve();
  return new Promise((resolve) => {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = prefs.rate;
    const chosen = pickBrowserVoice();
    if (chosen) utterance.voice = chosen;
    utterance.onend = resolve;
    utterance.onerror = resolve;
    if (gen !== speakGen) {
      resolve();
      return;
    }
    window.speechSynthesis.speak(utterance);
  });
}

function pickBrowserVoice() {
  const voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
  if (prefs.voice) {
    const match = voices.find((item) => item.name === prefs.voice || item.voiceURI === prefs.voice);
    if (match) return match;
  }
  const scored = voices
    .filter((item) => (item.lang || "").toLowerCase().startsWith("en"))
    .sort((a, b) => voiceScore(b) - voiceScore(a));
  return scored[0] || voices[0] || null;
}

function voiceScore(voice) {
  const lang = (voice.lang || "").toLowerCase();
  const name = (voice.name || "").toLowerCase();
  let score = 0;
  if (lang.startsWith("en-au")) score += 50;
  else if (lang.startsWith("en-gb")) score += 30;
  else if (lang.startsWith("en-us")) score += 10;
  if (name.includes("natural") || name.includes("neural") || name.includes("online")) score += 20;
  if (name.includes("google") || name.includes("microsoft")) score += 8;
  if (name.includes("catherine") || name.includes("hazel") || name.includes("sonia")) score += 12;
  if (name.includes("espeak") || name.includes("compact")) score -= 20;
  return score;
}

function fillVoices() {
  if (!voiceSelect) return;
  const current = prefs.voice;
  if (config.tts?.provider === "google") {
    voiceSelect.innerHTML = GOOGLE_VOICES.map(
      ([id, label]) => `<option value="${id}">${label}</option>`
    ).join("");
    const fallback = config.tts?.voice || GOOGLE_VOICES[0][0];
    voiceSelect.value = GOOGLE_VOICES.some(([id]) => id === current) ? current : fallback;
    prefs.voice = voiceSelect.value;
    return;
  }
  const voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
  const english = voices.filter((item) => (item.lang || "").toLowerCase().startsWith("en"));
  const list = (english.length ? english : voices).slice().sort((a, b) => voiceScore(b) - voiceScore(a));
  if (!list.length) {
    voiceSelect.innerHTML = '<option value="">Browser default</option>';
    return;
  }
  voiceSelect.innerHTML = list
    .map((item) => `<option value="${item.name}">${item.name} (${item.lang})</option>`)
    .join("");
  const best = pickBrowserVoice();
  if (current && list.some((item) => item.name === current)) voiceSelect.value = current;
  else if (best) voiceSelect.value = best.name;
  prefs.voice = voiceSelect.value;
}

if (voiceSelect) {
  voiceSelect.addEventListener("change", () => {
    prefs.voice = voiceSelect.value;
    localStorage.setItem("atlas.voice", prefs.voice);
  });
}
if (window.speechSynthesis) {
  window.speechSynthesis.addEventListener("voiceschanged", fillVoices);
}

function browserSpeech() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function mergePcm(chunks) {
  const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const out = new Float32Array(length);
  let offset = 0;
  chunks.forEach((chunk) => {
    out.set(chunk, offset);
    offset += chunk.length;
  });
  return out;
}

function encodeWav(float32, sampleRate) {
  const count = float32.length;
  const buffer = new ArrayBuffer(44 + count * 2);
  const view = new DataView(buffer);
  const write = (offset, text) => {
    for (let i = 0; i < text.length; i += 1) view.setUint8(offset + i, text.charCodeAt(i));
  };
  write(0, "RIFF");
  view.setUint32(4, 36 + count * 2, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  write(36, "data");
  view.setUint32(40, count * 2, true);
  let cursor = 44;
  for (let i = 0; i < count; i += 1) {
    const sample = Math.max(-1, Math.min(1, float32[i]));
    view.setInt16(cursor, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
    cursor += 2;
  }
  return new Blob([buffer], { type: "audio/wav" });
}

async function startListening() {
  if (listening) {
    await stopListening(true);
    return;
  }
  cancelled = false;
  stopSpeaking();
  const Speech = browserSpeech();
  if (Speech) {
    startBrowserSpeech(Speech);
    return;
  }
  if (config.stt?.provider === "none") {
    setStatus("No speech engine. Use Chrome/Edge, or set Whisper STT in Settings.");
    return;
  }
  await startWhisperCapture();
}

function startBrowserSpeech(Speech) {
  recognition = new Speech();
  recognition.lang = "en-AU";
  recognition.continuous = Boolean(prefs.twoWay);
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;
  listening = true;
  micBtn.classList.add("live");
  vu.classList.add("live");
  setLamp("listen", "listening");
  setStatus("Listening (browser speech). Pause when finished.");
  let finalText = "";
  recognition.onresult = (event) => {
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const piece = event.results[i][0].transcript;
      if (event.results[i].isFinal) finalText += `${piece} `;
      else interim += piece;
    }
    setStatus((finalText + interim).trim() || "Listening…");
    if (!prefs.twoWay && finalText.trim() && !interim) recognition.stop();
  };
  recognition.onerror = (event) => {
    if (event.error !== "no-speech" && event.error !== "aborted") {
      setStatus(`Mic error: ${event.error}`);
    }
  };
  recognition.onend = () => {
    const text = finalText.trim();
    listening = false;
    micBtn.classList.remove("live");
    vu.classList.remove("live");
    recognition = null;
    setLamp("idle", "idle");
    if (cancelled) {
      setStatus("");
      return;
    }
    if (!text) {
      setStatus("No speech heard. Click the mic and talk.");
      return;
    }
    setStatus("");
    inputEl.value = text;
    autosize();
    if (prefs.autoSend || prefs.twoWay) sendMessage(text);
  };
  try {
    recognition.start();
  } catch (error) {
    listening = false;
    setStatus(error.message);
  }
}

async function startWhisperCapture() {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
  });
  audioCtx = new AudioContext();
  await audioCtx.resume();
  pcmRate = audioCtx.sampleRate;
  pcmChunks = [];
  listening = true;
  const source = audioCtx.createMediaStreamSource(stream);
  const captureCode = `
    class AtlasCapture extends AudioWorkletProcessor {
      process(inputs) {
        const channel = inputs[0] && inputs[0][0];
        if (channel) this.port.postMessage(channel);
        return true;
      }
    }
    registerProcessor("atlas-capture", AtlasCapture);
  `;
  const url = URL.createObjectURL(new Blob([captureCode], { type: "application/javascript" }));
  await audioCtx.audioWorklet.addModule(url);
  URL.revokeObjectURL(url);
  workletNode = new AudioWorkletNode(audioCtx, "atlas-capture");
  workletNode.port.onmessage = (event) => {
    if (listening) pcmChunks.push(new Float32Array(event.data));
  };
  const mute = audioCtx.createGain();
  mute.gain.value = 0;
  source.connect(workletNode);
  workletNode.connect(mute);
  mute.connect(audioCtx.destination);
  workletNode._stream = stream;
  micBtn.classList.add("live");
  vu.classList.add("live");
  setLamp("listen", "listening");
  setStatus("Listening (Whisper). Pause to cut.");
  watchSilence(source);
}

function watchSilence(source) {
  const analyser = audioCtx.createAnalyser();
  analyser.fftSize = 2048;
  source.connect(analyser);
  const data = new Uint8Array(analyser.fftSize);
  let heard = false;
  let quietFor = 0;
  let last = performance.now();
  const bars = [...vu.querySelectorAll("span")];
  const loop = () => {
    if (!listening) return;
    analyser.getByteTimeDomainData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i += 1) {
      const v = (data[i] - 128) / 128;
      sum += v * v;
    }
    const rms = Math.sqrt(sum / data.length);
    bars.forEach((bar, index) => {
      bar.classList.toggle("on", rms > 0.02 + index * 0.018);
    });
    const now = performance.now();
    const dt = now - last;
    last = now;
    if (rms > 0.04) {
      heard = true;
      quietFor = 0;
    } else if (heard) {
      quietFor += dt;
      if (quietFor >= prefs.silenceMs) {
        stopListening(true);
        return;
      }
    }
    vuRaf = requestAnimationFrame(loop);
  };
  vuRaf = requestAnimationFrame(loop);
}

async function stopListening(transcribeNow) {
  if (!listening) return;
  if (recognition) {
    try {
      recognition.stop();
    } catch (_error) {
      /* already stopped */
    }
    return;
  }
  listening = false;
  micBtn.classList.remove("live");
  vu.classList.remove("live");
  vu.querySelectorAll("span").forEach((bar) => bar.classList.remove("on"));
  cancelAnimationFrame(vuRaf);
  const stream = workletNode && workletNode._stream;
  if (workletNode) {
    workletNode.port.onmessage = null;
    workletNode.disconnect();
    workletNode = null;
  }
  if (stream) stream.getTracks().forEach((track) => track.stop());
  if (audioCtx) {
    await audioCtx.close().catch(() => {});
    audioCtx = null;
  }
  setLamp("idle", "idle");
  const pcm = mergePcm(pcmChunks);
  pcmChunks = [];
  if (!transcribeNow) {
    setStatus("");
    return;
  }
  if (pcm.length < pcmRate * 0.4) {
    setStatus("Too short — hold the mic and speak a full sentence.");
    return;
  }
  setStatus("Transcribing with Whisper…");
  const blob = encodeWav(pcm, pcmRate);
  const form = new FormData();
  form.append("file", blob, "speech.wav");
  try {
    const response = await fetch("/api/voice/transcribe", { method: "POST", body: form });
    const data = await response.json().catch(() => ({}));
    const detail = data.detail;
    const message = typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : `HTTP ${response.status}`;
    if (!response.ok) throw new Error(message);
    if (!data.text) {
      setStatus("Heard audio, but Whisper returned no words. Try a clearer sentence.");
      return;
    }
    setStatus("");
    inputEl.value = data.text;
    autosize();
    if (prefs.autoSend || prefs.twoWay) sendMessage(data.text);
  } catch (error) {
    setStatus(error.message);
  }
}

function clearChannel() {
  cancelled = true;
  stopSpeaking();
  if (listening) stopListening(false);
  messagesEl.querySelectorAll(".msg").forEach((node) => node.remove());
  if (emptyEl) emptyEl.style.display = "";
  setStatus("");
  inputEl.focus();
}

document.getElementById("clear-btn").addEventListener("click", clearChannel);
document.getElementById("stop-btn").addEventListener("click", () => {
  haltAudio();
  if (listening) stopListening(false);
});
stopAudioBtn.addEventListener("click", haltAudio);
document.getElementById("preview-voice").addEventListener("click", () => {
  speak("ATLAS online. Grounded on company email.", { loop: false });
});
sendBtn.addEventListener("click", () => sendMessage());
inputEl.addEventListener("input", autosize);
inputEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
});

micBtn.addEventListener("pointerdown", (event) => {
  if (event.button !== 0) return;
  micBtn.setPointerCapture(event.pointerId);
  holdTalk = false;
  pressTimer = setTimeout(() => {
    holdTalk = true;
    if (!listening) startListening().catch((error) => setStatus(error.message));
  }, 220);
});
micBtn.addEventListener("pointerup", () => {
  clearTimeout(pressTimer);
  if (holdTalk) {
    holdTalk = false;
    if (listening) stopListening(true);
    return;
  }
  startListening().catch((error) => setStatus(error.message));
});
micBtn.addEventListener("pointercancel", () => {
  clearTimeout(pressTimer);
  holdTalk = false;
});

function syncVoiceHint() {
  const tts = config.tts?.provider === "google" ? `Google ${config.tts.voice || ""}`.trim() : "browser voice";
  const native = browserSpeech() ? "browser speech" : `Whisper ${config.stt?.provider || "off"}`;
  document.getElementById("voice-hint").textContent = `In: ${native}. Out: ${tts}.`;
}

async function loadStatus() {
  try {
    const [status, sources, cfg] = await Promise.all([
      api("/api/status"),
      api("/api/sources"),
      api("/api/config/public").catch(() => config),
    ]);
    config = cfg;
    document.getElementById("stat-model").textContent = status.llm.model;
    document.getElementById("stat-points").textContent = status.qdrant.points ?? sources.chunks;
    document.getElementById("stat-emails").textContent = sources.count;
    document.getElementById("channel-meta").textContent =
      `operator uplink · ${status.llm.model} · grounded on company email`;
    if (!Number(localStorage.getItem("atlas.speakRate")) && cfg.tts?.speaking_rate) {
      prefs.rate = Number(cfg.tts.speaking_rate);
      speakRate.value = String(prefs.rate);
      syncLabels();
    }
    syncVoiceHint();
    fillVoices();
  } catch (error) {
    document.getElementById("stat-model").textContent = "offline";
    setStatus(error.message);
  }
}

loadStatus();
inputEl.focus();
