import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import AskAI from "./AskAI";

export default function Layout() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-content">
        <Outlet />
      </main>
      <AskAI />
    </div>
  );
}