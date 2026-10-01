import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { login } from "../../api/client";
import { useAuth } from "../../context/AuthContext";

export default function Login() {
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const { signIn } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const res = await login(form);
      signIn(res.data.access_token, { user_id: res.data.user_id, role: res.data.role });
      const role = res.data.role;
      if (role === "buyer")  navigate("/buyer/dashboard");
      else if (role === "seller") navigate("/seller/dashboard");
      else navigate("/admin/dashboard");
    } catch (err) {
      setError(err.response?.data?.detail || "Login failed.");
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h2 style={styles.title}>TrustGrid Login</h2>
        {error && <p style={styles.error}>{error}</p>}
        <form onSubmit={handleSubmit}>
          <input style={styles.input} type="email" placeholder="Email"
            value={form.email} onChange={e => setForm({...form, email: e.target.value})} required />
          <input style={styles.input} type="password" placeholder="Password"
            value={form.password} onChange={e => setForm({...form, password: e.target.value})} required />
          <button style={styles.btn} type="submit">Login</button>
        </form>
        <p style={styles.link}>No account? <Link to="/register">Register</Link></p>
      </div>
    </div>
  );
}

const styles = {
  container: { display:"flex", justifyContent:"center", alignItems:"center", minHeight:"100vh", background:"#f7f8fa" },
  card: { background:"#fff", padding:"2rem", borderRadius:8, boxShadow:"0 2px 8px rgba(0,0,0,0.1)", width:360 },
  title: { textAlign:"center", marginBottom:"1.5rem", color:"#1f2328" },
  error: { color:"#c0392b", marginBottom:"1rem", textAlign:"center" },
  input: { display:"block", width:"100%", padding:"0.6rem", marginBottom:"1rem", border:"1px solid #e5e7eb", borderRadius:6, fontSize:14, boxSizing:"border-box" },
  btn:   { width:"100%", padding:"0.7rem", background:"#3b82d4", color:"#fff", border:"none", borderRadius:6, fontSize:15, cursor:"pointer" },
  link:  { textAlign:"center", marginTop:"1rem", fontSize:13, color:"#57606a" },
};
