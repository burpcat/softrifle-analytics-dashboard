import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

// Note: StrictMode intentionally double-invokes effects in development.
// API calls in useEffect will appear twice in the network tab — this is
// expected React 18 behaviour, not a bug. Do not remove StrictMode.
ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);