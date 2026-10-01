import { createContext, useContext, useState, useEffect } from "react";
import { getMe } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser]   = useState(null);
  const [token, setToken] = useState(localStorage.getItem("tg_token"));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (token) {
      getMe()
        .then((r) => setUser(r.data))
        .catch(() => { localStorage.removeItem("tg_token"); setToken(null); })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [token]);

  const signIn = (tok, userData) => {
    localStorage.setItem("tg_token", tok);
    setToken(tok);
    setUser(userData);
  };

  const signOut = () => {
    localStorage.removeItem("tg_token");
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
