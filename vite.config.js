import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const PREVIEW_API = process.env.PREVIEW_API || "http://127.0.0.1:8787";

// Hostnames phones / LAN clients use (machine is "bandit" on this network).
// Comma-separated override: VITE_ALLOWED_HOSTS=bandit,bandit.local,myhost
const extraAllowed = (process.env.VITE_ALLOWED_HOSTS || "")
  .split(",")
  .map((h) => h.trim())
  .filter(Boolean);

const defaultAllowedHosts = [
  "bandit",
  "bandit.local",
  "localhost",
  "127.0.0.1",
  ...extraAllowed,
];

// true = allow any Host header (LAN IPs + custom DNS names). Explicit list kept
// for clarity / env overrides; true wins so bandit + 192.168.x.x both work.
const allowAllHosts =
  process.env.VITE_ALLOW_ALL_HOSTS !== "0" &&
  process.env.VITE_ALLOW_ALL_HOSTS !== "false";

export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    // Bind all interfaces so phones / other LAN devices can open the preview
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    // Accept Host: bandit, bandit.local, LAN IPs, etc. (Vite 5+ host check)
    allowedHosts: allowAllHosts ? true : defaultAllowedHosts,
    // HMR over the same host the browser used (e.g. http://bandit:5173)
    hmr: {
      // client connects back to window.location.host; keep protocol/port stable
      clientPort: Number(process.env.UI_PORT || 5173),
    },
    proxy: {
      "/api": {
        target: PREVIEW_API,
        changeOrigin: true,
      },
      "/content": {
        target: PREVIEW_API,
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: "0.0.0.0",
    port: 4173,
    // Serves build.outDir (docs/) after `npm run build`
    allowedHosts: allowAllHosts ? true : defaultAllowedHosts,
  },
  build: {
    // Static site for GitHub Pages "Deploy from a branch" → /docs (no Actions required)
    outDir: "docs",
    emptyOutDir: true,
  },
});
