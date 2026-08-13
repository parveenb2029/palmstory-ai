// PalmStory AI — Phase 1 client (build artifact of frontend/src/*.ts).
// Handles the mobile nav, the capture/camera mock, and the mock processing
// pipeline. No AI is called here — the pipeline is simulated for the UI.

const $ = (id) => document.getElementById(id);

/* ---------- mobile nav ---------- */
(function nav() {
  const btn = $("menuBtn"), links = $("navLinks");
  if (!btn || !links) return;
  btn.addEventListener("click", () => {
    const open = links.classList.toggle("open");
    btn.setAttribute("aria-expanded", String(open));
  });
})();

/* ---------- capture page ---------- */
(function capture() {
  const app = $("captureApp");
  if (!app) return;

  const state = { hand: "right", stream: null, facing: "environment", captured: null };
  const video = $("video"), shot = $("shot"), guide = $("guide"),
        stage = $("stage"), stageMsg = $("stageMsg"),
        capBar = $("capBar"), file = $("file");

  // hand selection
  app.querySelectorAll(".hand-pick button").forEach((b) => {
    b.addEventListener("click", () => {
      state.hand = b.dataset.hand;
      app.querySelectorAll(".hand-pick button").forEach((x) =>
        x.setAttribute("aria-pressed", String(x === b)));
    });
  });

  async function startCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return camError({ name: "Unsupported" });
    }
    try {
      state.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: state.facing }, audio: false,
      });
      video.srcObject = state.stream;
      video.muted = true;
      video.classList.remove("hidden");
      guide.classList.remove("hidden");
      stageMsg.classList.add("hidden");
      try { await video.play(); }
      catch (e) { video.onloadedmetadata = () => video.play().catch(() => {}); }
    } catch (err) {
      // rear cam may not exist on laptops — retry with any camera
      if (["OverconstrainedError", "NotFoundError", "NotReadableError"].includes(err.name)) {
        try {
          state.stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
          video.srcObject = state.stream; video.muted = true;
          video.classList.remove("hidden"); guide.classList.remove("hidden");
          await video.play().catch(() => {});
          return;
        } catch (e2) { return camError(e2); }
      }
      camError(err);
    }
  }
  function stopCamera() {
    if (state.stream) { state.stream.getTracks().forEach((t) => t.stop()); state.stream = null; }
    video.srcObject = null;
  }
  function camError(err) {
    video.classList.add("hidden"); guide.classList.add("hidden");
    stageMsg.classList.remove("hidden");
    const inFrame = (() => { try { return window.self !== window.top; } catch (e) { return true; } })();
    if (inFrame) {
      stageMsg.innerHTML = "This preview window blocks the camera. <b>Open the page in its own browser tab</b> on localhost or https — then the camera works. You can upload a photo instead.";
    } else if (err.name === "NotAllowedError" || err.name === "SecurityError") {
      stageMsg.innerHTML = "Camera access was blocked. <b>Allow camera</b> in your browser, or upload a photo instead.";
    } else if (err.name === "Unsupported" || !window.isSecureContext) {
      stageMsg.innerHTML = "The camera needs a secure page (<b>https</b> or localhost). You can upload a photo instead.";
    } else {
      stageMsg.innerHTML = "No camera available. You can <b>upload a photo</b> of your palm instead.";
    }
  }

  // capture a still (mock quality check)
  function capture() {
    if (!state.stream) return;
    const w = video.videoWidth, h = video.videoHeight;
    const c = document.createElement("canvas"); c.width = w; c.height = h;
    const ctx = c.getContext("2d");
    ctx.translate(w, 0); ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0, w, h);
    state.captured = c.toDataURL("image/jpeg", 0.9);
    stopCamera();
    goReview();
  }
  function fromFile(f) {
    const reader = new FileReader();
    reader.onload = (e) => { state.captured = e.target.result; stopCamera(); goReview(); };
    reader.readAsDataURL(f);
  }

  function goReview() {
    $("reviewShot").src = state.captured;
    $("captureStep").classList.add("hidden");
    $("reviewStep").classList.remove("hidden");
    showQuality(state.captured);
  }
  function goCapture() {
    shot.classList.add("hidden");
    $("reviewStep").classList.add("hidden");
    $("captureStep").classList.remove("hidden");
    startCamera();
  }

  /* ---------- image quality gate (client-side, pre-AI) ----------
     Heuristic checks so we never spend AI on an unusable photo. Authoritative
     palm detection + quality comes server-side with MediaPipe in Phase 4. */
  const Q = { DARK: 55, BRIGHT: 220, BLUR: 60, MIN_RES: 320, EMPTY: 40 };

  function analyzeQuality(dataUrl) {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => {
        const W = img.naturalWidth, H = img.naturalHeight;
        const n = 220, scale = Math.min(1, n / Math.max(W, H));
        const w = Math.max(1, Math.round(W * scale)), h = Math.max(1, Math.round(H * scale));
        const c = document.createElement("canvas"); c.width = w; c.height = h;
        const ctx = c.getContext("2d", { willReadFrequently: true });
        ctx.drawImage(img, 0, 0, w, h);
        const px = ctx.getImageData(0, 0, w, h).data;

        const gray = new Float32Array(w * h);
        let sum = 0;
        for (let i = 0, p = 0; i < px.length; i += 4, p++) {
          const g = 0.299 * px[i] + 0.587 * px[i + 1] + 0.114 * px[i + 2];
          gray[p] = g; sum += g;
        }
        const brightness = sum / (w * h);

        // sharpness: variance of a Laplacian (low = blurry)
        let ls = 0, ls2 = 0, cnt = 0;
        for (let y = 1; y < h - 1; y++)
          for (let x = 1; x < w - 1; x++) {
            const i = y * w + x;
            const lap = 4 * gray[i] - gray[i - 1] - gray[i + 1] - gray[i - w] - gray[i + w];
            ls += lap; ls2 += lap * lap; cnt++;
          }
        const sharpness = ls2 / cnt - (ls / cnt) ** 2;

        // center content: near-uniform centre → probably no palm / blank wall
        const x0 = (w * 0.25) | 0, x1 = (w * 0.75) | 0, y0 = (h * 0.25) | 0, y1 = (h * 0.75) | 0;
        let cs = 0, cs2 = 0, cc = 0;
        for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) { const g = gray[y * w + x]; cs += g; cs2 += g * g; cc++; }
        const centerVar = cs2 / cc - (cs / cc) ** 2;

        const reasons = [];
        if (brightness < Q.DARK) reasons.push("It's a little dark — move into better light.");
        if (brightness > Q.BRIGHT) reasons.push("Too bright — soften glare or harsh light.");
        if (sharpness < Q.BLUR) reasons.push("Looks blurry — hold steady and try again.");
        if (Math.min(W, H) < Q.MIN_RES) reasons.push("Low resolution — use a larger, closer photo.");
        if (centerVar < Q.EMPTY && sharpness >= Q.BLUR) reasons.push("I can't see a palm clearly — fill the outline with your open palm.");

        const bScore = 1 - Math.min(1, Math.abs(brightness - 140) / 140);
        const sScore = Math.min(1, sharpness / 220);
        const usable = reasons.length === 0;
        const score = Math.round(((usable ? 1 : 0.4) * 0.4 + bScore * 0.3 + sScore * 0.3) * 100);
        resolve({ usable, score, reasons, metrics: { brightness: Math.round(brightness), sharpness: Math.round(sharpness), resolution: W + "×" + H } });
      };
      img.onerror = () => resolve({ usable: true, score: 70, reasons: [], metrics: {} });
      img.src = dataUrl;
    });
  }

  async function showQuality(dataUrl) {
    const el = $("qualityResult"), submit = $("submitBtn");
    el.className = "quality"; el.innerHTML = '<span class="quality-checking">Checking lighting, focus &amp; framing…</span>';
    submit.disabled = true;
    const q = await analyzeQuality(dataUrl);
    const m = q.metrics;
    if (q.usable) {
      el.className = "quality ok";
      el.innerHTML = "<strong>Looks good ✓</strong><span class=\"qmeta\">brightness " + m.brightness + " · sharpness " + m.sharpness + " · " + m.resolution + "</span>";
      submit.disabled = false;
    } else {
      el.className = "quality warn";
      el.innerHTML = "<strong>Let's retake this one</strong><ul>" + q.reasons.map((r) => "<li>" + r + "</li>").join("") + "</ul>";
      submit.disabled = true;
    }
  }

  // pipeline: create an async job, then poll it — the UI reflects real progress
  async function runPipeline() {
    $("reviewStep").classList.add("hidden");
    $("procStep").classList.remove("hidden");
    const list = $("procList").children;   // [analyze, features, reading, comic]
    const titles = ["Analyzing your palm…", "Understanding features…",
                    "Writing your story…", "Illustrating your story…"];
    // backend stage → UI step index
    const stageStep = { queued: 0, analyzing: 0, interpreting: 1, writing: 2,
                        storyboard: 2, illustrating: 3, done: 3 };

    function paint(step, progress) {
      for (let k = 0; k < list.length; k++)
        list[k].className = k < step ? "done" : (k === step ? "active" : "");
      $("procTitle").textContent = titles[Math.min(step, titles.length - 1)];
      $("procBar").style.width = (progress || (step + 1) * 25) + "%";
    }

    function backToReview(reasons) {
      $("procStep").classList.add("hidden");
      $("reviewStep").classList.remove("hidden");
      const el = $("qualityResult");
      el.className = "quality warn";
      el.innerHTML = "<strong>Let's retake this one</strong>" +
        (reasons && reasons.length ? "<ul>" + reasons.map((r) => "<li>" + r + "</li>").join("") + "</ul>" : "");
      $("submitBtn").disabled = true;
    }

    paint(0, 10);
    let jobId = null;
    try {
      const res = await fetch("/api/v1/readings", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: state.captured, hand: state.hand }),
      });
      const data = await res.json();
      if (data.status === "rejected" || (data.quality && !data.quality.usable)) {
        return backToReview(data.quality ? data.quality.reasons : []);
      }
      jobId = data.job_id;
    } catch (e) {
      // backend unreachable — client gate already passed, go to the reading
      return void (window.location.href = "/history");
    }
    if (!jobId) return void (window.location.href = "/history");

    // poll the job until it finishes
    const poll = async () => {
      try {
        const r = await fetch("/api/v1/readings/" + jobId);
        const s = await r.json();
        if (s.status === "failed") {
          backToReview(["Something went wrong generating your reading. Please try again."]);
          return;
        }
        paint(stageStep[s.stage] ?? 0, s.progress);
        if (s.status === "complete") {
          $("procTitle").textContent = "Your reading is ready!";
          setTimeout(() => (window.location.href = "/reading/" + (s.reading_id || "")), 600);
          return;
        }
      } catch (e) { /* transient — keep polling */ }
      setTimeout(poll, 700);
    };
    poll();
  }

  $("shutter")?.addEventListener("click", capture);
  $("uploadBtn")?.addEventListener("click", () => file.click());
  file?.addEventListener("change", () => file.files[0] && fromFile(file.files[0]));
  $("switchBtn")?.addEventListener("click", () => {
    state.facing = state.facing === "environment" ? "user" : "environment";
    stopCamera(); startCamera();
  });
  $("retakeBtn")?.addEventListener("click", goCapture);
  $("submitBtn")?.addEventListener("click", runPipeline);

  startCamera();
})();
