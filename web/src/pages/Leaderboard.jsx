import React, { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export default function Leaderboard() {
  const { email } = useAuth();
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState(null);
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const run = async () => {
      setError("");
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/leaderboard?limit=200`, {
          headers: { Authorization: `Bearer ${email}` },
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setSummary(data.summary);
        setRows(data.rows || []);
      } catch (e) {
        setError(e.message || "Failed to fetch leaderboard");
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [email]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <h1 className="text-2xl font-semibold">Leaderboard</h1>
      <p className="text-sm text-zinc-400">Recall@K (Faithfulness coming soon)</p>

      {/* Summary */}
      <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
          <div className="text-xs text-zinc-400">Average Recall@K</div>
          <div className="text-2xl font-bold">
            {summary ? (summary.avg_recall?.toFixed(3) ?? "–") : "…"}
          </div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
          <div className="text-xs text-zinc-400">Evaluations</div>
          <div className="text-2xl font-bold">{summary ? summary.n_evals : "…"}</div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
          <div className="text-xs text-zinc-400">Last Run</div>
          <div className="text-2xl font-bold">
            {summary && summary.last_eval_at ? new Date(summary.last_eval_at).toLocaleString() : "–"}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="mt-6 rounded-lg border border-zinc-800 overflow-hidden">
        <div className="bg-zinc-900 px-4 py-2 text-sm text-zinc-400 flex justify-between">
          <span>Recent Evaluations</span>
          {loading && <span>Loading…</span>}
        </div>
        {error && <div className="p-4 text-red-400 text-sm">{error}</div>}
        <div className="divide-y divide-zinc-800">
          {rows.length === 0 && !loading ? (
            <div className="p-4 text-sm text-zinc-400">No evaluations yet.</div>
          ) : (
            rows.map((r) => (
              <div key={r.eval_id} className="p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="font-medium">{r.query_text}</div>
                  <div className="text-xs text-zinc-400">Eval #{r.eval_id} · Trace #{r.trace_id}</div>
                </div>
                <div className="mt-2 text-sm text-zinc-300 flex flex-wrap gap-4">
                  <span>Recall@K: <span className="font-semibold">{r.recall_at_k.toFixed(3)}</span></span>
                  <span>K: <span className="font-semibold">{r.top_k}</span></span>
                  <span>Hits: <span className="font-mono text-xs break-all">{r.hits.join(", ")}</span></span>
                </div>
                <div className="mt-1 text-xs text-zinc-500">
                  Gold Chunks: <span className="font-mono break-all">{r.gold_chunks.join(", ")}</span>
                </div>
                <div className="mt-1 text-xs text-zinc-500">
                  {new Date(r.created_at).toLocaleString()}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
