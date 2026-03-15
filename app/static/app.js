// app.js — SpotLite frontend

const state = {
    ws: null,
    config: null,
    audioContext: null,
    playbackContext: null,
    micStream: null,
    micProcessor: null,
    isRecording: false,
    bomItems: [],
    bomTotal: 0,
    bomBudget: 0,
    imageHistory: [],
    cameraStream: null,
    cameraInterval: null,
};

// In-progress user transcript element
let _pendingUserTranscript = null;

// ============ Setup Screen ============

// Auto-detect city via geolocation on page load
(function autoDetectLocation() {
    if (!navigator.geolocation) return;
    const locationInput = document.getElementById("location");
    navigator.geolocation.getCurrentPosition(
        async (pos) => {
            try {
                const { latitude, longitude } = pos.coords;
                const resp = await fetch(
                    `https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json&accept-language=id`
                );
                const data = await resp.json();
                const city = data.address?.city || data.address?.town || data.address?.county || data.address?.state || "";
                if (city && locationInput && !locationInput.value) {
                    locationInput.value = city;
                    locationInput.placeholder = "e.g., Jakarta Selatan";
                }
            } catch (e) {
                console.warn("Reverse geocode failed:", e);
                locationInput.placeholder = "e.g., Jakarta Selatan";
            }
        },
        () => {
            locationInput.placeholder = "e.g., Jakarta Selatan";
        },
        { timeout: 5000 }
    );
})();

function startSession() {
    const name = document.getElementById("show-name").value || "Untitled Show";
    const width = parseFloat(document.getElementById("stage-width").value) || 8;
    const depth = parseFloat(document.getElementById("stage-depth").value) || 6;
    const height = parseFloat(document.getElementById("stage-height").value) || 4;
    const budget = parseInt(document.getElementById("budget").value) || 25000000;
    const location = document.getElementById("location").value || "";

    state.config = { name, width, depth, height, budget, location };

    document.getElementById("setup-screen").style.display = "none";
    document.getElementById("session-screen").style.display = "grid";
    document.getElementById("budget-text").textContent =
        `Rp 0 / Rp ${budget.toLocaleString("id-ID")}`;

    connectWebSocket();
}

// ============ WebSocket ============

function connectWebSocket() {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${location.host}/ws/session`;
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        state.ws.send(JSON.stringify({
            type: "start_session",
            config: state.config,
        }));
    };

    state.ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type !== "audio") {
            console.log("WS msg:", msg.type, msg);
        }
        handleServerMessage(msg);
    };

    state.ws.onclose = (event) => {
        updateVoiceStatus("Disconnected — refresh to reconnect");
        stopPeriodicCapture();
        if (!event.wasClean) {
            addTranscript("assistant", "Connection lost. Please refresh the page to start a new session.");
        }
    };

    state.ws.onerror = () => {
        updateVoiceStatus("Connection error");
    };
}

function handleServerMessage(msg) {
    switch (msg.type) {
        case "session_started":
            updateVoiceStatus("Ready — tap mic to start talking");
            showBaseStagePlaceholder();
            break;
        case "audio":
            playAudioChunk(msg.data);
            break;
        case "transcript":
            addTranscript(msg.role, msg.text);
            break;
        case "user_transcript":
            handleUserTranscript(msg.text, msg.finished);
            break;
        case "assistant_transcript":
            handleAssistantTranscript(msg.text, msg.finished);
            break;
        case "stage_image":
            showStageImage(msg.data, msg.mime_type);
            break;
        case "bom":
            updateBOM(msg);
            break;
        case "vendor_results":
            showVendorResults(msg);
            break;
        case "vendor_search_started":
            showVendorSearchStarted(msg);
            break;
        case "vendor_result":
            showVendorResultPanel(msg);
            break;
        case "vendor_search_complete":
            hideVendorSkeletons();
            break;
        case "thrift_result":
            showThriftResult(msg);
            break;
        case "error":
            addTranscript("assistant", "Error: " + msg.message);
            break;
    }
}

// ============ User Transcription ============

function handleUserTranscript(text, finished) {
    const log = document.getElementById("transcript-log");

    if (!finished) {
        // Update in-progress element
        if (!_pendingUserTranscript) {
            _pendingUserTranscript = document.createElement("div");
            _pendingUserTranscript.className = "transcript-entry user partial";
            log.appendChild(_pendingUserTranscript);
        }
        _pendingUserTranscript.textContent = text;
    } else {
        // Finalize
        if (_pendingUserTranscript) {
            _pendingUserTranscript.textContent = text;
            _pendingUserTranscript.classList.remove("partial");
            _pendingUserTranscript = null;
        } else {
            addTranscript("user", text);
        }
    }
    log.scrollTop = log.scrollHeight;
}

// ============ Assistant Transcription ============

let _pendingAssistantTranscript = null;

function handleAssistantTranscript(text, finished) {
    const log = document.getElementById("transcript-log");

    if (!finished) {
        if (!_pendingAssistantTranscript) {
            _pendingAssistantTranscript = document.createElement("div");
            _pendingAssistantTranscript.className = "transcript-entry assistant partial";
            log.appendChild(_pendingAssistantTranscript);
        }
        _pendingAssistantTranscript.textContent = text;
    } else {
        if (_pendingAssistantTranscript) {
            _pendingAssistantTranscript.textContent = text;
            _pendingAssistantTranscript.classList.remove("partial");
            _pendingAssistantTranscript = null;
        } else {
            addTranscript("assistant", text);
        }
    }
    log.scrollTop = log.scrollHeight;
}

// ============ Vendor Results ============

function showVendorResults(msg) {
    const log = document.getElementById("transcript-log");
    const card = document.createElement("div");
    card.className = "transcript-entry vendor-card";

    let html = `<strong>Vendor Search: ${msg.query || ""}</strong>`;
    html += `<p>${msg.text || "No results found."}</p>`;

    if (msg.sources && msg.sources.length > 0) {
        html += '<div class="vendor-sources">';
        for (const src of msg.sources) {
            html += `<a href="${src.url}" target="_blank" rel="noopener">${src.title || src.url}</a>`;
        }
        html += "</div>";
    }

    card.innerHTML = html;
    log.appendChild(card);
    log.scrollTop = log.scrollHeight;
}

// ============ Vendor Panel ============

function showVendorSearchStarted(msg) {
    const container = document.getElementById("vendor-results-container");
    container.innerHTML = "";
    for (const itemName of (msg.items || [])) {
        const skeleton = document.createElement("div");
        skeleton.className = "vendor-card-panel loading";
        skeleton.dataset.itemName = itemName;
        skeleton.innerHTML = `
            <strong>${itemName}</strong>
            <div class="skeleton-bar"></div>
            <div class="skeleton-bar short"></div>
        `;
        container.appendChild(skeleton);
    }
}

function showVendorResultPanel(msg) {
    const container = document.getElementById("vendor-results-container");
    const skeleton = container.querySelector(`[data-item-name="${CSS.escape(msg.item_name)}"]`);

    const card = document.createElement("div");
    card.className = "vendor-card-panel";

    // Truncate text to ~200 chars for compact display
    const summary = (msg.text || "").substring(0, 200).replace(/\n+/g, " ");
    let html = `<strong>${msg.item_name}</strong>`;
    html += `<p class="vendor-text">${summary}${msg.text?.length > 200 ? "..." : ""}</p>`;

    if (msg.sources?.length) {
        html += '<div class="vendor-links">';
        for (const src of msg.sources) {
            const label = src.title || new URL(src.url).hostname;
            html += `<a href="${src.url}" target="_blank" rel="noopener">${label}</a>`;
        }
        html += "</div>";
    }

    card.innerHTML = html;
    if (skeleton) skeleton.replaceWith(card);
    else container.appendChild(card);
}

function showThriftResult(msg) {
    const container = document.getElementById("vendor-results-container");
    const card = document.createElement("div");
    card.className = "vendor-card-panel thrift";

    const summary = (msg.text || "").substring(0, 250).replace(/\n+/g, " ");
    let html = `<strong>Toko Rongsokan & Barang Bekas</strong>`;
    html += `<p class="vendor-text">${summary}${msg.text?.length > 250 ? "..." : ""}</p>`;

    if (msg.sources?.length) {
        html += '<div class="vendor-links">';
        for (const src of msg.sources) {
            const label = src.title || "Maps";
            html += `<a href="${src.url}" target="_blank" rel="noopener">${label}</a>`;
        }
        html += "</div>";
    }

    card.innerHTML = html;
    container.appendChild(card);
}

function hideVendorSkeletons() {
    const container = document.getElementById("vendor-results-container");
    container.querySelectorAll(".vendor-card-panel.loading").forEach((el) => el.remove());
}

// ============ Audio Capture ============

async function initAudio() {
    state.audioContext = new AudioContext({ sampleRate: 16000 });
    state.micStream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true },
    });
}

async function toggleMic() {
    const btn = document.getElementById("btn-mic");

    if (!state.isRecording) {
        if (!state.audioContext) await initAudio();

        const source = state.audioContext.createMediaStreamSource(state.micStream);
        state.micProcessor = state.audioContext.createScriptProcessor(4096, 1, 1);

        state.micProcessor.onaudioprocess = (e) => {
            if (!state.isRecording || !state.ws || state.ws.readyState !== 1) return;
            const float32 = e.inputBuffer.getChannelData(0);
            const int16 = float32ToInt16(float32);
            const b64 = arrayBufferToBase64(int16.buffer);
            state.ws.send(JSON.stringify({ type: "audio", data: b64 }));
        };

        source.connect(state.micProcessor);
        state.micProcessor.connect(state.audioContext.destination);

        state.isRecording = true;
        btn.classList.add("active");
        updateVoiceStatus("Listening...");
    } else {
        state.isRecording = false;
        if (state.micProcessor) {
            state.micProcessor.disconnect();
            state.micProcessor = null;
        }
        btn.classList.remove("active");
        updateVoiceStatus("Mic muted — tap to unmute");
    }
}

function float32ToInt16(float32Array) {
    const int16 = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
        const s = Math.max(-1, Math.min(1, float32Array[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return int16;
}

// ============ Audio Playback ============

let nextPlayTime = 0;
let playbackEndTimer = null;

function playAudioChunk(b64Data) {
    const bytes = base64ToArrayBuffer(b64Data);

    if (!state.playbackContext) {
        state.playbackContext = new AudioContext({ sampleRate: 24000 });
    }
    const ctx = state.playbackContext;

    const int16 = new Int16Array(bytes);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 0x7fff;
    }

    const buffer = ctx.createBuffer(1, float32.length, 24000);
    buffer.getChannelData(0).set(float32);

    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);

    const now = ctx.currentTime;
    if (nextPlayTime < now) {
        nextPlayTime = now;
    }
    source.start(nextPlayTime);

    if (nextPlayTime <= now) {
        if (state.isRecording) {
            updateVoiceStatus("SpotLite is speaking... (listening)");
        } else {
            updateVoiceStatus("SpotLite is speaking...");
        }
    }

    nextPlayTime += buffer.duration;

    clearTimeout(playbackEndTimer);
    const remaining = nextPlayTime - ctx.currentTime;
    playbackEndTimer = setTimeout(() => {
        if (state.isRecording) {
            updateVoiceStatus("Listening...");
        } else {
            updateVoiceStatus("Mic muted — tap to unmute");
        }
    }, remaining * 1000 + 50);
}

// ============ Camera ============

async function captureStage() {
    const video = document.getElementById("camera-preview");
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: "environment", width: 1280, height: 720 },
        });
        video.srcObject = stream;
        await video.play();

        await new Promise((r) => setTimeout(r, 500));

        const b64 = captureFrame(video);
        showStageImage(b64, "image/jpeg");

        if (state.ws) {
            state.ws.send(JSON.stringify({ type: "photo", data: b64 }));
        }

        // Keep stream alive for periodic captures
        state.cameraStream = stream;
        video.classList.add("pip-visible");
        startPeriodicCapture(video);

        addTranscript("user", "[Captured stage photo — live vision active]");
    } catch (err) {
        alert("Camera access denied or not available: " + err.message);
    }
}

function captureFrame(video) {
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    return canvas.toDataURL("image/jpeg", 0.6).split(",")[1];
}

function startPeriodicCapture(video) {
    stopPeriodicCapture();
    state.cameraInterval = setInterval(() => {
        if (!state.ws || state.ws.readyState !== 1) return;
        if (!video.srcObject) return;
        const b64 = captureFrame(video);
        state.ws.send(JSON.stringify({ type: "photo", data: b64 }));
    }, 10000);
}

function stopPeriodicCapture() {
    if (state.cameraInterval) {
        clearInterval(state.cameraInterval);
        state.cameraInterval = null;
    }
    if (state.cameraStream) {
        state.cameraStream.getTracks().forEach((t) => t.stop());
        state.cameraStream = null;
    }
    const video = document.getElementById("camera-preview");
    video.srcObject = null;
    video.classList.remove("pip-visible");
}

// ============ UI Updates ============

function updateVoiceStatus(text) {
    const el = document.getElementById("voice-status");
    const indicator = document.getElementById("voice-indicator");
    el.textContent = text;
    el.className = "voice-status";
    indicator.className = "voice-indicator";

    if (text.includes("Listening")) {
        el.classList.add("listening");
        indicator.classList.add("listening");
    } else if (text.includes("speaking")) {
        el.classList.add("speaking");
        indicator.classList.add("speaking");
    }
}

function addTranscript(role, text) {
    const log = document.getElementById("transcript-log");
    const entry = document.createElement("div");
    entry.className = `transcript-entry ${role}`;
    entry.textContent = text;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

function showBaseStagePlaceholder() {
    const container = document.getElementById("stage-image-container");
    container.innerHTML = `<img src="/static/stage.png" alt="Placeholder stage">`;
}

function showStageImage(b64, mimeType) {
    const container = document.getElementById("stage-image-container");

    // Save previous image to history
    const currentImg = container.querySelector("img");
    if (currentImg && currentImg.src.startsWith("data:")) {
        state.imageHistory.push(currentImg.src);
        renderImageHistory();
    }

    // Remove loading state
    container.classList.remove("loading");

    // Show new image
    container.innerHTML = `<img src="data:${mimeType || "image/png"};base64,${b64}" alt="Stage design">`;
}

function renderImageHistory() {
    const strip = document.getElementById("image-history");
    if (!strip) return;
    strip.innerHTML = "";
    state.imageHistory.forEach((src, i) => {
        const thumb = document.createElement("img");
        thumb.src = src;
        thumb.alt = `Design ${i + 1}`;
        thumb.title = `Design ${i + 1} — click to view`;
        thumb.onclick = () => showFullSizeOverlay(src, i + 1);
        strip.appendChild(thumb);
    });
}

function showFullSizeOverlay(src, num) {
    const overlay = document.createElement("div");
    overlay.className = "image-overlay";
    overlay.innerHTML = `
        <div class="overlay-content">
            <span class="overlay-label">Design ${num}</span>
            <img src="${src}" alt="Design ${num}">
            <button class="overlay-close" onclick="this.closest('.image-overlay').remove()">Close</button>
        </div>
    `;
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
    document.body.appendChild(overlay);
}

function updateBOM(data) {
    state.bomItems = data.items || [];
    state.bomTotal = data.total || 0;
    state.bomBudget = data.budget || state.config.budget;

    const tbody = document.getElementById("bom-body");
    tbody.innerHTML = "";

    if (state.bomItems.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="color:#555; text-align:center;">No matching materials found</td></tr>';
        return;
    }

    for (const item of state.bomItems) {
        const tr = document.createElement("tr");
        tr.className = "bom-row-enter";
        tr.innerHTML = `
            <td>${item.name}</td>
            <td class="number">${item.quantity}</td>
            <td>${item.unit || "-"}</td>
            <td class="number">Rp ${(item.unit_price || 0).toLocaleString("id-ID")}</td>
            <td class="number">Rp ${(item.subtotal || 0).toLocaleString("id-ID")}</td>
        `;
        tbody.appendChild(tr);
    }

    const pct = Math.min((state.bomTotal / state.bomBudget) * 100, 100);
    const progress = document.getElementById("budget-progress");
    progress.value = pct;
    progress.className = "progress w-full";
    if (pct > 90) progress.classList.add("progress-error");
    else if (pct > 70) progress.classList.add("progress-warning");
    else progress.classList.add("progress-success");

    document.getElementById("budget-text").textContent =
        `Rp ${state.bomTotal.toLocaleString("id-ID")} / Rp ${state.bomBudget.toLocaleString("id-ID")}`;
}

function exportBOM() {
    if (state.bomItems.length === 0) return;

    let csv = "Item,Quantity,Unit,Unit Price (Rp),Subtotal (Rp)\n";
    for (const item of state.bomItems) {
        csv += `"${item.name}",${item.quantity},"${item.unit}",${item.unit_price},${item.subtotal}\n`;
    }
    csv += `\nTotal,,,,${state.bomTotal}\n`;
    csv += `Budget,,,,${state.bomBudget}\n`;
    csv += `Remaining,,,,${state.bomBudget - state.bomTotal}\n`;

    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "spotlite-bom.csv";
    a.click();
}

// ============ Utilities ============

function arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    for (let i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
}

function base64ToArrayBuffer(base64) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
}
