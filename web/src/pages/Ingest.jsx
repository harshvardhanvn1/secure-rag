import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export default function Ingest() {
  const { email } = useAuth();
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState("");
  const [sourceKey, setSourceKey] = useState("");
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const handleFileUpload = async (e) => {
    e.preventDefault();
    if (!file) return setError("Choose a file first.");
    setError("");
    setMessage("");
    setLoading(true);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(`${API_BASE}/ingest_file`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${email}`,   
        },
        body: formData,
      });

      if (!res.ok) throw new Error(await res.text() || `Upload failed (${res.status})`);
      const data = await res.json();
      setMessage(`Uploaded: ${data.title || file.name} (${data.chunks} chunks)`);
    } catch (err) {
      setError(err.message || "Upload error.");
    } finally {
      setLoading(false);
      setFile(null);
    }
  };

  const handleTextIngest = async (e) => {
    e.preventDefault();
    if (!text.trim()) return setError("Enter some text.");
    setError("");
    setMessage("");
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/ingest`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${email}`,   // ✅ fixed
        },
        body: JSON.stringify({
          title: title || "Untitled",
          source_key: sourceKey || undefined,
          text: text.trim(),
        }),
      });

      if (!res.ok) throw new Error(await res.text() || `Ingest failed (${res.status})`);
      const data = await res.json();
      setMessage(`Ingested: ${data.title || title} (${data.chunks} chunks)`);
    } catch (err) {
      setError(err.message || "Ingest error.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-6 text-zinc-100">
      <h1 className="text-xl font-semibold mb-4">Ingest</h1>

      {/* File upload */}
      <form
        onSubmit={handleFileUpload}
        className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 mb-6"
      >
        <label className="block mb-2">Upload .pdf or .txt</label>
        <input
          type="file"
          accept=".pdf,.txt"
          className="mb-3"
          onChange={(e) => setFile(e.target.files[0])}
        />
        <button
          type="submit"
          disabled={loading}
          className="bg-red-600 hover:bg-red-700 disabled:opacity-60 text-white px-4 py-2 rounded"
        >
          {loading ? "Uploading..." : "Upload"}
        </button>
      </form>

      {/* Raw text ingest */}
      <form
        onSubmit={handleTextIngest}
        className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5"
      >
        <label className="block mb-2">Paste raw text</label>
        <input
          type="text"
          placeholder="Document title"
          className="w-full mb-3 bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <input
          type="text"
          placeholder="Optional source_key"
          className="w-full mb-3 bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm"
          value={sourceKey}
          onChange={(e) => setSourceKey(e.target.value)}
        />
        <textarea
          placeholder="Paste text here..."
          rows={6}
          className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <button
          type="submit"
          disabled={loading}
          className="mt-3 bg-red-600 hover:bg-red-700 disabled:opacity-60 text-white px-4 py-2 rounded"
        >
          {loading ? "Submitting..." : "Ingest Text"}
        </button>
      </form>

      {/* Status */}
      {message && <div className="mt-4 text-green-400 text-sm">{message}</div>}
      {error && <div className="mt-4 text-red-400 text-sm">{error}</div>}
    </div>
  );
}
