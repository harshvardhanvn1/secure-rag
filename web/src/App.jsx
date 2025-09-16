import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Navbar from "./components/Navbar";
import { useAuth } from "./context/AuthContext";

import Login from "./pages/Login";
import Ingest from "./pages/Ingest";
import Search from "./pages/Search";
import Leaderboard from "./pages/Leaderboard";
import Security from "./pages/Security";

function Protected({ children }) {
  const { isAuthed } = useAuth();
  return isAuthed ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <Routes>
        <Route path="/" element={<Navigate to="/search" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/ingest" element={<Protected><Ingest /></Protected>} />
        <Route path="/search" element={<Protected><Search /></Protected>} />
        <Route path="/leaderboard" element={<Protected><Leaderboard /></Protected>} />
        <Route path="/security" element={<Protected><Security /></Protected>} />
        <Route path="*" element={<Navigate to="/search" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
