import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import "./index.css";

// Legacy hash routes (#/article/slug) → path routes for social previews
if (typeof window !== "undefined") {
  const hash = window.location.hash || "";
  const m = hash.match(/^#\/?(article\/[^?#]+)/i);
  if (m) {
    const path = `/${m[1].replace(/\/$/, "")}`;
    window.location.replace(`${path}${window.location.search}`);
  }
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
