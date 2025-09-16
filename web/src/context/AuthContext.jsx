import React, { createContext, useContext, useState } from "react";

const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [email, setEmail] = useState(() => localStorage.getItem("sr_email") || "");
  const isAuthed = Boolean(email);

  const login = (val) => {
    const e = (val || "").trim();
    if (!e) return;
    localStorage.setItem("sr_email", e);
    setEmail(e);
  };

  const logout = () => {
    localStorage.removeItem("sr_email");
    setEmail("");
  };

  return (
    <AuthContext.Provider value={{ email, isAuthed, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
