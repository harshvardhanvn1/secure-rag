import React, { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

function KTable({ title, rows }) {
  return (
    <div className="rounded-lg border border-zinc-800 overflow-hidden">
      <div className="bg-zinc-900 px-4 py-2 text-sm text-zinc-400">{title}</div>
      <div className="divide-y divide-zinc-800">
        {rows && rows.length ? rows.map((r, i) => (
          <div key={i} className="p-3 text-sm flex items-center justify-between">
            <span className="font-mono">{r.entity_type}</span>
            <span className="font-semibold">{r.total}</span>
          </div>
        )) : <div className="p-3 text-sm text-zinc-400">No data.</div>}
      </div>
    </div>
  );
}

export default function Security() {
  const { email } = useAuth();
  const [stats, setStats] = useState({ totals: [], last_7d: [], last_24h: [] });
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    const run = async () => {
      setLoading(true); setErr("");
      try {
        const [s, r] = await Promise.all([
          fetch(`${API_BASE}/security_stats`, { headers: { Authorization: `Bearer ${email}` } }),
          fetch(`${API_BASE}/security_runs?limit=20`, { headers: { Authorization: `Bearer ${email}` } }),
        ]);
        if (!s.ok) throw new Error(`stats HTTP ${s.status}`);
        if (!r.ok) throw new Error(`runs HTTP ${r.status}`);
        setStats(await s.json());
        setRuns(await r.json());
      } catch (e) {
        setErr(e.message || "Failed to fetch");
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [email]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <h1 className="text-2xl font-semibold">Security</h1>
      <p className="text-sm text-zinc-400">PII redaction stats & evaluation</p>

      {err && <div className="mt-4 text-red-400 text-sm">{String(err)}</div>}
      {loading && <div className="mt-4 text-sm text-zinc-400">Loading…</div>}

      {/* Totals */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
        <KTable title="All-time totals" rows={stats.totals} />
        <KTable title="Last 7 days" rows={stats.last_7d} />
        <KTable title="Last 24 hours" rows={stats.last_24h} />
      </div>

      {/* Runs */}
      <div className="mt-6 rounded-lg border border-zinc-800 overflow-hidden">
        <div className="bg-zinc-900 px-4 py-2 text-sm text-zinc-400">Recent PII Evaluation Runs</div>
        <div className="divide-y divide-zinc-800">
          {!runs.length ? (
            <div className="p-4 text-sm text-zinc-400">No runs yet. Run <code>scripts/synthetic_pii_eval.py</code>.</div>
          ) : runs.map(r => (
            <div key={r.run_id} className="p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="font-medium">Run #{r.run_id}</div>
                <div className="text-xs text-zinc-500">{new Date(r.created_at).toLocaleString()}</div>
              </div>
              <div className="mt-2 text-sm text-zinc-300 flex flex-wrap gap-4">
                <span>Precision: <span className="font-semibold">{r.micro_precision.toFixed(3)}</span></span>
                <span>Recall: <span className="font-semibold">{r.micro_recall.toFixed(3)}</span></span>
                <span>F1: <span className="font-semibold">{r.micro_f1.toFixed(3)}</span></span>
              </div>
              {r.notes && <div className="mt-1 text-xs text-zinc-500">Notes: {r.notes}</div>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
