import { defineConfig } from "vite";
import { resolve } from "path";

// Builds the TypeScript entry into a single static/js/app.js that FastAPI serves.
export default defineConfig({
  build: {
    outDir: "static/js",
    emptyOutDir: false,
    lib: {
      entry: resolve(__dirname, "frontend/src/main.ts"),
      formats: ["es"],
      fileName: () => "app.js",
    },
  },
});
