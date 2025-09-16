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
        <div className="flex items-center gap-6">
          <Link to="/" className="text-lg font-semibold tracking-wide">
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
            </>
          )}
        </div>
        <div className="flex items-center gap-3">
          {isAuthed ? (
            <>
              <span className="text-xs text-zinc-400">{email}</span>
              <button
                onClick={handleLogout}
                className="text-xs bg-red-600 hover:bg-red-700 text-white px-3 py-1.5 rounded"
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
