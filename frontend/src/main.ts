// PalmStory AI — client entry (TypeScript source).
// Build output is served from /static/js/app.js. Phase 1 keeps the logic small;
// as the app grows this splits into typed modules (camera, pipeline, api).
//
//   cd .. && npm install && npm run build   # emits static/js/app.js
//
// The committed static/js/app.js is the current build so the app runs with just
// Python. Keep this source and that artifact in sync as features grow.

import { initNav } from "./nav";
import { initCapture } from "./camera";

initNav();
initCapture();
