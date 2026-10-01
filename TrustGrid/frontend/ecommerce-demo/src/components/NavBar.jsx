import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function NavBar() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => { signOut(); navigate("/login"); };

  const links = user?.role === "buyer"
    ? [["Products", "/buyer/products"],["Orders", "/buyer/orders"],["Trust", "/buyer/trust"]]
    : user?.role === "seller"
    ? [["Add Product", "/seller/add-product"],["Orders", "/seller/orders"],["Trust", "/seller/trust"]]
    : [["Dashboard", "/admin/dashboard"]];

  return (
    <nav style={{ background:"#1f2328", padding:"0 1.5rem", display:"flex", alignItems:"center", height:52, gap:24 }}>
      <span style={{ color:"#fff", fontWeight:700, fontSize:17, marginRight:16 }}>TrustGrid</span>
      {links.map(([label, to]) => (
        <Link key={to} to={to} style={{ color:"#c9d1d9", textDecoration:"none", fontSize:14 }}>{label}</Link>
      ))}
      <span style={{ flex:1 }} />
      {user && (
        <>
          <span style={{ color:"#8b949e", fontSize:13 }}>{user.user_id}</span>
          <button onClick={handleLogout} style={{ padding:"4px 12px", background:"transparent", color:"#8b949e", border:"1px solid #30363d", borderRadius:5, cursor:"pointer", fontSize:13 }}>
            Logout
          </button>
        </>
      )}
    </nav>
  );
}
