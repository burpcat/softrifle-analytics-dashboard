import { useState, useRef, useEffect } from "react";

// --- Typing indicator ---
function TypingDots() {
  return (
    <div className="flex items-center gap-1 px-4 py-3">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-2 h-2 rounded-full bg-slate-400 animate-bounce"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  );
}

// --- Individual message bubble ---
function Message({ role, text }) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap leading-relaxed ${
          isUser
            ? "bg-blue-600 text-white rounded-br-sm"
            : "bg-slate-100 text-slate-800 rounded-bl-sm"
        }`}
      >
        {text}
      </div>
    </div>
  );
}

// --- Main component ---
export default function AskAI() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  // Scroll to bottom whenever messages or loading state changes
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Focus input when panel opens
  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  async function handleSend() {
    const question = input.trim();
    if (!question || loading) return;

    setInput("");
    setError(null);
    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setLoading(true);

    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Something went wrong");
      }

      setMessages((prev) => [...prev, { role: "ai", text: data.answer }]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">
      {/* --- Expanded panel --- */}
      {open && (
        <div className="flex flex-col w-96 h-[500px] bg-white border border-slate-200 rounded-2xl shadow-2xl overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-white">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-green-400" />
              <span className="font-semibold text-slate-800 text-sm">HardScope AI</span>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="text-slate-400 hover:text-slate-600 transition-colors text-lg leading-none"
              aria-label="Close"
            >
              ✕
            </button>
          </div>

          {/* Chat history */}
          <div className="flex-1 overflow-y-auto px-4 py-4">
            {messages.length === 0 && (
              <p className="text-slate-400 text-sm text-center mt-16">
                Ask anything about your creators or campaigns.
              </p>
            )}
            {messages.map((msg, i) => (
              <Message key={i} role={msg.role} text={msg.text} />
            ))}
            {loading && (
              <div className="flex justify-start mb-3">
                <div className="bg-slate-100 rounded-2xl rounded-bl-sm">
                  <TypingDots />
                </div>
              </div>
            )}
            {error && (
              <p className="text-red-500 text-xs text-center mt-2">{error}</p>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input bar */}
          <div className="px-3 py-3 border-t border-slate-200 bg-white flex gap-2">
            <textarea
              ref={inputRef}
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question…"
              disabled={loading}
              className="flex-1 resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || loading}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white rounded-xl px-4 py-2 text-sm font-medium transition-colors"
            >
              Send
            </button>
          </div>
        </div>
      )}

      {/* --- Floating toggle button --- */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-3 rounded-full shadow-lg transition-colors text-sm font-medium"
      >
        <span>{open ? "✕" : "💬"}</span>
        {!open && <span>Ask AI</span>}
      </button>
    </div>
  );
}