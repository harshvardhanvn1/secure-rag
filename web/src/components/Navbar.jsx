import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Navbar() {
  const { email, isAuthed, logout } = useAuth();
  const nav = useNavigate();

  const handleLogout = () => {
    logout();
    nav("/login");
  };

  return (
    <nav className="w-full bg-zinc-900 text-zinc-100 border-b border-zinc-800">
      <div className="mx-auto max-w-6xl flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-4">
          <Link to="/search" className="font-semibold hover:text-white">
            Secure-RAG
          </Link>
          {isAuthed && (
            <>
              <Link to="/ingest" className="text-sm text-zinc-300 hover:text-zinc-100">
                Ingest
              </Link>
              <Link to="/search" className="text-sm text-zinc-300 hover:text-zinc-100">
                Search
              </Link>
              <Link to="/leaderboard" className="text-sm text-zinc-300 hover:text-zinc-100">
                Leaderboard
              </Link>
              <Link to="/security" className="text-sm text-zinc-300 hover:text-zinc-100">
                Security
              </Link>
            </>
          )}
        </div>
        <div className="flex items-center gap-3">
          {isAuthed ? (
            <>
              <span className="text-xs text-zinc-400">{email}</span>
              <button
                onClick={handleLogout}
                className="text-sm bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded px-3 py-1.5"
              >
                Logout
              </button>
            </>
          ) : (
            <Link to="/login" className="text-sm text-zinc-300 hover:text-zinc-100">
              Login
            </Link>
          )}
        </div>
      </div>
    </nav>
  );
}
