/**
 * TrustGrid Dashboard — shown to buyers and sellers.
 * Spec §22: Trust Score/1000, Tier, Confidence, 5 dimensions, recent changes,
 *           benefits, improvement tip, score history chart.
 */
import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { getMyTrust, getTrustHistory, recalculateTrust } from "../../api/client";
import { useAuth } from "../../context/AuthContext";

const TIER_COLORS = { RESTRICTED:"#c0392b", STANDARD:"#f39c12", TRUSTED:"#27ae60", ELITE:"#8e44ad" };
const CONF_COLORS = { LOW:"#e74c3c", MEDIUM:"#f39c12", HIGH:"#27ae60" };

function DimBar({ name, value }) {
  const pct = Math.round(value);
  const color = pct >= 70 ? "#27ae60" : pct >= 40 ? "#f39c12" : "#e74c3c";
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display:"flex", justifyContent:"space-between", fontSize:13, marginBottom:3 }}>
        <span>{name.replace(/_/g," ").replace(/\b\w/g,c=>c.toUpperCase())}</span>
        <span style={{ fontWeight:600 }}>{pct}/100</span>
      </div>
      <div style={{ background:"#e5e7eb", borderRadius:4, height:8 }}>
        <div style={{ width:`${pct}%`, background:color, borderRadius:4, height:"100%", transition:"width 0.4s" }} />
      </div>
    </div>
  );
}

export default function TrustDashboard() {
  const { user } = useAuth();
  const [trust, setTrust]     = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const [tr, hist] = await Promise.all([
        getMyTrust(),
        user?.user_id ? getTrustHistory(user.user_id) : Promise.resolve({ data: [] }),
      ]);
      setTrust(tr.data);
      // Build chart data from history (most recent last)
      const chartData = [...(hist.data || [])].reverse().map((h, i) => ({
        name: `#${i+1}`, score: h.new_score,
      }));
      setHistory(chartData);
    } catch (e) {
      setError("Could not load trust data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleRecalc = async () => {
    await recalculateTrust();
    load();
  };

  if (loading) return <p style={{ padding:"2rem" }}>Loading trust data…</p>;
  if (error)   return <p style={{ padding:"2rem", color:"red" }}>{error}</p>;
  if (!trust)  return null;

  const tierColor = TIER_COLORS[trust.tier] || "#3b82d4";
  const confColor = CONF_COLORS[trust.confidence] || "#57606a";
  const exp = trust.explanation || {};

  return (
    <div style={{ padding:"1.5rem", maxWidth:860, margin:"0 auto", fontFamily:"system-ui,sans-serif" }}>
      {/* Header row */}
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:"1.5rem" }}>
        <h2 style={{ margin:0, color:"#1f2328" }}>TrustGrid Dashboard</h2>
        <button onClick={handleRecalc}
          style={{ padding:"0.5rem 1rem", background:"#3b82d4", color:"#fff", border:"none", borderRadius:6, cursor:"pointer", fontSize:13 }}>
          Recalculate
        </button>
      </div>

      {/* Score card */}
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:16, marginBottom:"1.5rem" }}>
        <ScoreCard label="Trust Score" value={`${trust.trust_score}/1000`} color={tierColor} />
        <ScoreCard label="Tier" value={trust.tier} color={tierColor} />
        <ScoreCard label="Confidence" value={trust.confidence} color={confColor} />
      </div>

      {/* Five dimensions */}
      <SectionBox title="Dimension Breakdown">
        {Object.entries(trust.breakdown || {}).map(([k, v]) => (
          <DimBar key={k} name={k} value={v} />
        ))}
        {exp.weakest_dimension && (
          <p style={{ marginTop:12, fontSize:13, color:"#57606a" }}>
            💡 <strong>Improve:</strong> {exp.improvement_tip}
          </p>
        )}
      </SectionBox>

      {/* Score history chart */}
      {history.length > 1 && (
        <SectionBox title="Score History">
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={history}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="name" tick={{ fontSize:11 }} />
              <YAxis domain={[0,1000]} tick={{ fontSize:11 }} />
              <Tooltip />
              <Line type="monotone" dataKey="score" stroke="#3b82d4" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </SectionBox>
      )}

      {/* Recent changes */}
      {exp.score_change !== undefined && (
        <SectionBox title="Latest Score Change">
          <p style={{ margin:0, fontSize:14 }}>{exp.summary}</p>
          <p style={{ margin:"6px 0 0", fontSize:13, color:confColor }}>{exp.confidence_note}</p>
        </SectionBox>
      )}

      {/* Benefits */}
      <SectionBox title="Your Benefits">
        {(trust.benefits || []).length === 0
          ? <p style={{ color:"#57606a", margin:0, fontSize:13 }}>No active benefits yet.</p>
          : <div style={{ display:"flex", flexWrap:"wrap", gap:8 }}>
              {trust.benefits.map(b => (
                <span key={b} style={{ background:"#eaf3ff", color:"#3b82d4", padding:"4px 12px", borderRadius:20, fontSize:13 }}>
                  {b.replace(/_/g," ")}
                </span>
              ))}
            </div>
        }
      </SectionBox>

      {/* Positive / Negative factors */}
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16 }}>
        <SectionBox title="✅ Positive Factors">
          {(exp.positive_factors||[]).length === 0
            ? <p style={{color:"#57606a",margin:0,fontSize:13}}>None yet.</p>
            : (exp.positive_factors||[]).map(f=>(
                <p key={f} style={{margin:"2px 0",fontSize:13,color:"#27ae60"}}>
                  {f.replace(/_/g," ")}
                </p>
              ))}
        </SectionBox>
        <SectionBox title="⚠️ Areas to Improve">
          {(exp.negative_factors||[]).length === 0
            ? <p style={{color:"#57606a",margin:0,fontSize:13}}>None identified.</p>
            : (exp.negative_factors||[]).map(f=>(
                <p key={f} style={{margin:"2px 0",fontSize:13,color:"#e74c3c"}}>
                  {f.replace(/_/g," ")}
                </p>
              ))}
        </SectionBox>
      </div>
    </div>
  );
}

function ScoreCard({ label, value, color }) {
  return (
    <div style={{ background:"#fff", border:"1px solid #e5e7eb", borderRadius:8, padding:"1rem", textAlign:"center" }}>
      <div style={{ fontSize:12, color:"#57606a", marginBottom:4 }}>{label}</div>
      <div style={{ fontSize:22, fontWeight:700, color }}>{value}</div>
    </div>
  );
}

function SectionBox({ title, children }) {
  return (
    <div style={{ background:"#fff", border:"1px solid #e5e7eb", borderRadius:8, padding:"1rem", marginBottom:"1rem" }}>
      <h4 style={{ margin:"0 0 0.75rem", color:"#1f2328", fontSize:14, fontWeight:600 }}>{title}</h4>
      {children}
    </div>
  );
}
