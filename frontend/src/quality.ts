// Client-side image-quality gate (TypeScript source; see static/js/app.js for
// the built artifact). Heuristic pre-checks so we never spend AI on an unusable
// photo. Authoritative palm detection + quality is server-side (MediaPipe) in
// Phase 4.

export interface QualityResult {
  usable: boolean;
  score: number;
  reasons: string[];
  metrics: { brightness?: number; sharpness?: number; resolution?: string };
}

const Q = { DARK: 55, BRIGHT: 220, BLUR: 60, MIN_RES: 320, EMPTY: 40 };

export function analyzeQuality(dataUrl: string): Promise<QualityResult> {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const W = img.naturalWidth, H = img.naturalHeight;
      const n = 220, scale = Math.min(1, n / Math.max(W, H));
      const w = Math.max(1, Math.round(W * scale)), h = Math.max(1, Math.round(H * scale));
      const c = document.createElement("canvas"); c.width = w; c.height = h;
      const ctx = c.getContext("2d", { willReadFrequently: true })!;
      ctx.drawImage(img, 0, 0, w, h);
      const px = ctx.getImageData(0, 0, w, h).data;

      const gray = new Float32Array(w * h);
      let sum = 0;
      for (let i = 0, p = 0; i < px.length; i += 4, p++) {
        const g = 0.299 * px[i] + 0.587 * px[i + 1] + 0.114 * px[i + 2];
        gray[p] = g; sum += g;
      }
      const brightness = sum / (w * h);

      let ls = 0, ls2 = 0, cnt = 0;
      for (let y = 1; y < h - 1; y++)
        for (let x = 1; x < w - 1; x++) {
          const i = y * w + x;
          const lap = 4 * gray[i] - gray[i - 1] - gray[i + 1] - gray[i - w] - gray[i + w];
          ls += lap; ls2 += lap * lap; cnt++;
        }
      const sharpness = ls2 / cnt - (ls / cnt) ** 2;

      const x0 = (w * 0.25) | 0, x1 = (w * 0.75) | 0, y0 = (h * 0.25) | 0, y1 = (h * 0.75) | 0;
      let cs = 0, cs2 = 0, cc = 0;
      for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) { const g = gray[y * w + x]; cs += g; cs2 += g * g; cc++; }
      const centerVar = cs2 / cc - (cs / cc) ** 2;

      const reasons: string[] = [];
      if (brightness < Q.DARK) reasons.push("It's a little dark — move into better light.");
      if (brightness > Q.BRIGHT) reasons.push("Too bright — soften glare or harsh light.");
      if (sharpness < Q.BLUR) reasons.push("Looks blurry — hold steady and try again.");
      if (Math.min(W, H) < Q.MIN_RES) reasons.push("Low resolution — use a larger, closer photo.");
      if (centerVar < Q.EMPTY && sharpness >= Q.BLUR) reasons.push("I can't see a palm clearly — fill the outline with your open palm.");

      const bScore = 1 - Math.min(1, Math.abs(brightness - 140) / 140);
      const sScore = Math.min(1, sharpness / 220);
      const usable = reasons.length === 0;
      const score = Math.round(((usable ? 1 : 0.4) * 0.4 + bScore * 0.3 + sScore * 0.3) * 100);
      resolve({ usable, score, reasons, metrics: { brightness: Math.round(brightness), sharpness: Math.round(sharpness), resolution: `${W}×${H}` } });
    };
    img.onerror = () => resolve({ usable: true, score: 70, reasons: [], metrics: {} });
    img.src = dataUrl;
  });
}
