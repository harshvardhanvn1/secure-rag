import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export default function Search() {
  const { email } = useAuth();
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [traceId, setTraceId] = useState("");
  const [hits, setHits] = useState([]);
  const [error, setError] = useState("");

  const doSearch = async () => {
    setError("");
    setTraceId("");
    setHits([]);

    if (!query.trim()) return setError("Enter a query.");
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/search`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${email}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query: query.trim(), top_k: Number(topK) || 5 }),
      });

      if (!res.ok) throw new Error(await res.text() || `Search failed (${res.status})`);

      const data = await res.json();
      console.log("Search API response:", data); // 👈 debug log

      setTraceId(data.trace_id || "");
      setHits(Array.isArray(data.hits) ? data.hits : []);
    } catch (err) {
      console.error("Search error:", err);
      setError(err.message || "Search error.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 text-zinc-100">
      <h1 className="text-xl font-semibold mb-4">Search</h1>

      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
        <div className="flex flex-col md:flex-row gap-3">
          <input
            className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm"
            placeholder="Ask a question…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="flex flex-col">
            <label className="text-xs text-zinc-400 mb-1">Top-K Matches</label>
            <input
              type="number"
              min={1}
              max={50}
              className="w-24 bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm"
              value={topK}
              onChange={(e) => setTopK(e.target.value)}
            />
          </div>
          <button
            onClick={doSearch}
            disabled={loading}
            className="bg-red-600 hover:bg-red-700 disabled:opacity-60 text-white px-4 py-2 rounded self-end"
          >
            {loading ? "Searching…" : "Search"}
          </button>
        </div>

        {error && <div className="mt-3 text-sm text-red-400">{error}</div>}

        {traceId && (
          <div className="mt-4 text-xs text-zinc-400">
            trace_id: <span className="text-zinc-200">{traceId}</span>
          </div>
        )}

        {hits.length > 0 && (
          <div className="mt-6">
            <h2 className="text-sm font-semibold text-zinc-300 mb-3">
              Top {hits.length} Matches
            </h2>
            <div className="space-y-3">
              {hits.map((h) => (
                <div key={`${h.rank}-${h.chunk_id}`} className="bg-zinc-950 border border-zinc-800 rounded-xl p-4">
                  <div className="text-xs text-zinc-400 mb-1">
                    Rank {h.rank} • Score {(h.score * 100).toFixed(1)}%
                  </div>
                  <div className="font-medium">{h.title}</div>
                  <div className="text-sm text-zinc-300 mt-1 whitespace-pre-wrap">
                    {h.snippet}
                  </div>
                  <div className="text-xs text-zinc-500 mt-2">chunk_id: {h.chunk_id}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
