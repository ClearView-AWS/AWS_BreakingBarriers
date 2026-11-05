import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { captureStaffCode } from "./staff";
import "./styles.css";

captureStaffCode();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
