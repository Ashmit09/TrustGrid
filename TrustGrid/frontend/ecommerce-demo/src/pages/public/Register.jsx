import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { register } from "../../api/client";
import { useAuth } from "../../context/AuthContext";

export default function Register() {
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "buyer" });
  const [error, setError] = useState("");
  const { signIn } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const res = await register(form);
      signIn(res.data.access_token, { user_id: res.data.user_id, role: res.data.role });
      navigate(form.role === "buyer" ? "/buyer/dashboard" : "/seller/dashboard");
    } catch (err) {
      setError(err.response?.data?.detail || "Registration failed.");
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h2 style={styles.title}>Join TrustGrid</h2>
        {error && <p style={styles.error}>{error}</p>}
        <form onSubmit={handleSubmit}>
          <input style={styles.input} placeholder="Full Name"
            value={form.name} onChange={e => setForm({...form, name: e.target.value})} required />
          <input style={styles.input} type="email" placeholder="Email"
            value={form.email} onChange={e => setForm({...form, email: e.target.value})} required />
          <input style={styles.input} type="password" placeholder="Password (min 8 chars)"
            value={form.password} onChange={e => setForm({...form, password: e.target.value})} required />
          <select style={styles.input} value={form.role} onChange={e => setForm({...form, role: e.target.value})}>
            <option value="buyer">Buyer</option>
            <option value="seller">Seller</option>
          </select>
          <button style={styles.btn} type="submit">Create Account</button>
        </form>
        <p style={styles.link}>Already have an account? <Link to="/login">Login</Link></p>
      </div>
    </div>
  );
}

const styles = {
  container: { display:"flex", justifyContent:"center", alignItems:"center", minHeight:"100vh", background:"#f7f8fa" },
  card: { background:"#fff", padding:"2rem", borderRadius:8, boxShadow:"0 2px 8px rgba(0,0,0,0.1)", width:380 },
  title: { textAlign:"center", marginBottom:"1.5rem", color:"#1f2328" },
  error: { color:"#c0392b", marginBottom:"1rem", textAlign:"center" },
  input: { display:"block", width:"100%", padding:"0.6rem", marginBottom:"1rem", border:"1px solid #e5e7eb", borderRadius:6, fontSize:14, boxSizing:"border-box" },
  btn:   { width:"100%", padding:"0.7rem", background:"#3b82d4", color:"#fff", border:"none", borderRadius:6, fontSize:15, cursor:"pointer" },
  link:  { textAlign:"center", marginTop:"1rem", fontSize:13, color:"#57606a" },
};
