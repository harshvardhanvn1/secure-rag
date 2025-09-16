import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const nav = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    const value = email.trim().toLowerCase();
    if (!value) return setError("Please enter your email.");

    try {
      setChecking(true);
      // Call the backend /login endpoint instead of /healthz
      const res = await fetch(`${API_BASE}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: value }),
      });
      if (!res.ok) throw new Error(`Login failed (${res.status})`);
      const data = await res.json();

      // backend returns { token: email }
      login(data.token);
      nav("/ingest");
    } catch (err) {
      setError(err.message || "Login failed.");
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="flex min-h-[calc(100vh-56px)] items-center justify-center bg-zinc-950 text-zinc-100 px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md bg-zinc-900 border border-zinc-800 rounded-2xl p-6"
      >
        <h1 className="text-xl font-semibold mb-4">Login</h1>
        <p className="text-sm text-zinc-400 mb-6">
          Enter your email. All requests will include{" "}
          <code className="px-1 bg-zinc-800 rounded">Authorization: Bearer &lt;email&gt;</code>.
        </p>
        <label className="text-sm block mb-2">Email</label>
        <input
          type="email"
          className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-600"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        {error && <div className="text-red-400 text-xs mt-2">{error}</div>}
        <button
          type="submit"
          disabled={checking}
          className="mt-6 w-full bg-red-600 hover:bg-red-700 disabled:opacity-60 text-white rounded px-3 py-2 text-sm"
        >
          {checking ? "Checking..." : "Continue"}
        </button>
      </form>
    </div>
  );
}
