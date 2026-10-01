import { useEffect, useState } from "react";
import { adminAnalytics, adminUsers, trustDistribution } from "../../api/client";
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";

const TIER_COLORS = { RESTRICTED:"#e74c3c", STANDARD:"#f39c12", TRUSTED:"#27ae60", ELITE:"#8e44ad" };

export default function AdminDashboard() {
  const [analytics, setAnalytics] = useState(null);
  const [dist, setDist] = useState(null);
  const [users, setUsers] = useState([]);

  useEffect(() => {
    adminAnalytics().then(r => setAnalytics(r.data)).catch(() => {});
    trustDistribution().then(r => setDist(r.data)).catch(() => {});
    adminUsers().then(r => setUsers(r.data)).catch(() => {});
  }, []);

  const tierPieData = dist
    ? Object.entries(dist.tier_distribution).map(([name, value]) => ({ name, value }))
    : [];

  return (
    <div style={{ padding:"1.5rem", fontFamily:"system-ui,sans-serif" }}>
      <h2 style={{ color:"#1f2328" }}>Admin Dashboard</h2>

      {analytics && (
        <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12, marginBottom:24 }}>
          {[["Total Users", analytics.total_users],
            ["Buyers", analytics.total_buyers],
            ["Sellers", analytics.total_sellers],
            ["Score Changes", analytics.total_score_changes]].map(([l,v]) => (
            <div key={l} style={{ background:"#fff", border:"1px solid #e5e7eb", borderRadius:8, padding:"1rem", textAlign:"center" }}>
              <div style={{ fontSize:12, color:"#57606a", marginBottom:4 }}>{l}</div>
              <div style={{ fontSize:24, fontWeight:700, color:"#3b82d4" }}>{v}</div>
            </div>
          ))}
        </div>
      )}

      {dist && (
        <div style={{ background:"#fff", border:"1px solid #e5e7eb", borderRadius:8, padding:"1rem", marginBottom:24 }}>
          <h4 style={{ margin:"0 0 12px", color:"#1f2328" }}>Tier Distribution</h4>
          <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center" }}>
            <ResponsiveContainer width="50%" height={200}>
              <PieChart>
                <Pie data={tierPieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80}>
                  {tierPieData.map(entry => (
                    <Cell key={entry.name} fill={TIER_COLORS[entry.name] || "#3b82d4"} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
            <div>
              <p style={{ margin:0 }}>Average Score: <strong>{dist.average_trust_score}</strong></p>
            </div>
          </div>
        </div>
      )}

      <div style={{ background:"#fff", border:"1px solid #e5e7eb", borderRadius:8, padding:"1rem" }}>
        <h4 style={{ margin:"0 0 12px", color:"#1f2328" }}>All Users ({users.length})</h4>
        <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
          <thead>
            <tr style={{ background:"#f7f8fa" }}>
              {["User ID","Name","Email","Role"].map(h => (
                <th key={h} style={{ textAlign:"left", padding:"8px 12px", border:"1px solid #e5e7eb" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {users.slice(0,50).map(u => (
              <tr key={u.user_id}>
                <td style={{ padding:"6px 12px", border:"1px solid #e5e7eb" }}>{u.user_id}</td>
                <td style={{ padding:"6px 12px", border:"1px solid #e5e7eb" }}>{u.name}</td>
                <td style={{ padding:"6px 12px", border:"1px solid #e5e7eb" }}>{u.email}</td>
                <td style={{ padding:"6px 12px", border:"1px solid #e5e7eb" }}>{u.role}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
