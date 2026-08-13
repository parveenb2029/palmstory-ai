// Capture flow (TypeScript source). Mirrors static/js/app.js.
// Phase 3 replaces the mock pipeline with real quality checks + a job request.

type Facing = "environment" | "user";

interface CaptureState {
  hand: "left" | "right";
  stream: MediaStream | null;
  facing: Facing;
  captured: string | null;
}

const $ = (id: string) => document.getElementById(id);

export function initCapture(): void {
  const app = $("captureApp");
  if (!app) return;

  const state: CaptureState = { hand: "right", stream: null, facing: "environment", captured: null };
  const video = $("video") as HTMLVideoElement;
  const shot = $("shot") as HTMLImageElement;
  const guide = $("guide")!;
  const stageMsg = $("stageMsg")!;
  const file = $("file") as HTMLInputElement;

  app.querySelectorAll<HTMLButtonElement>(".hand-pick button").forEach((b) => {
    b.addEventListener("click", () => {
      state.hand = (b.dataset.hand as "left" | "right");
      app.querySelectorAll<HTMLButtonElement>(".hand-pick button").forEach((x) =>
        x.setAttribute("aria-pressed", String(x === b)));
    });
  });

  async function startCamera(): Promise<void> {
    if (!navigator.mediaDevices?.getUserMedia) return camError({ name: "Unsupported" } as DOMException);
    try {
      state.stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: state.facing }, audio: false });
      video.srcObject = state.stream;
      video.muted = true;
      video.classList.remove("hidden");
      guide.classList.remove("hidden");
      stageMsg.classList.add("hidden");
      try { await video.play(); } catch { video.onloadedmetadata = () => void video.play().catch(() => {}); }
    } catch (err) {
      const e = err as DOMException;
      if (["OverconstrainedError", "NotFoundError", "NotReadableError"].includes(e.name)) {
        try {
          state.stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
          video.srcObject = state.stream; video.muted = true;
          video.classList.remove("hidden"); guide.classList.remove("hidden");
          await video.play().catch(() => {});
          return;
        } catch (e2) { return camError(e2 as DOMException); }
      }
      camError(e);
    }
  }

  function stopCamera(): void {
    state.stream?.getTracks().forEach((t) => t.stop());
    state.stream = null;
    video.srcObject = null;
  }

  function camError(err: DOMException): void {
    video.classList.add("hidden"); guide.classList.add("hidden");
    stageMsg.classList.remove("hidden");
    let inFrame = true;
    try { inFrame = window.self !== window.top; } catch { inFrame = true; }
    if (inFrame) stageMsg.innerHTML = "This preview window blocks the camera. <b>Open the page in its own browser tab</b> on localhost or https. You can upload a photo instead.";
    else if (err.name === "NotAllowedError" || err.name === "SecurityError") stageMsg.innerHTML = "Camera access was blocked. <b>Allow camera</b> or upload a photo.";
    else stageMsg.innerHTML = "No camera available. You can <b>upload a photo</b> instead.";
  }

  // capture, review, and the mock pipeline live here in the full source;
  // see static/js/app.js for the complete Phase 1 behaviour.
  void shot; void file; void stopCamera;
  startCamera();
}
