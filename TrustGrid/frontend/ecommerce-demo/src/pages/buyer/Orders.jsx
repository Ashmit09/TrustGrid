import { useEffect, useState } from "react";
import { listOrders, cancelOrder, payOrder, submitReview } from "../../api/client";

export default function Orders() {
  const [orders, setOrders] = useState([]);
  const [msg, setMsg] = useState("");

  const load = () => listOrders().then(r => setOrders(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const action = async (fn, ...args) => {
    try { await fn(...args); load(); setMsg("Done!"); setTimeout(() => setMsg(""), 2000); }
    catch (e) { setMsg(e.response?.data?.detail || "Error"); }
  };

  const STATUS_COLOR = { PLACED:"#3b82d4", COMPLETED:"#27ae60", CANCELLED:"#e74c3c",
    ACCEPTED:"#8e44ad", SHIPPED:"#f39c12", DELIVERED:"#27ae60" };

  return (
    <div style={{ padding:"1.5rem" }}>
      <h2>My Orders</h2>
      {msg && <p style={{ color:"#27ae60" }}>{msg}</p>}
      {orders.length === 0 && <p>No orders yet.</p>}
      {orders.map(o => (
        <div key={o.order_id} style={{ border:"1px solid #e5e7eb", borderRadius:8, padding:"1rem", marginBottom:12, background:"#fff" }}>
          <div style={{ display:"flex", justifyContent:"space-between", marginBottom:6 }}>
            <strong>{o.order_id}</strong>
            <span style={{ color: STATUS_COLOR[o.status] || "#57606a", fontSize:13 }}>{o.status}</span>
          </div>
          <p style={{ margin:"0 0 8px", fontSize:13, color:"#57606a" }}>
            Amount: ₦{o.total_amount} | Qty: {o.quantity}
          </p>
          <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
            {o.status === "PLACED" && (
              <>
                <Btn onClick={() => action(payOrder, o.order_id, "CARD_SIMULATED")} label="Pay" />
                <Btn onClick={() => action(cancelOrder, o.order_id)} label="Cancel" red />
              </>
            )}
            {(o.status === "DELIVERED" || o.status === "COMPLETED") && (
              <Btn onClick={() => action(submitReview, o.order_id, { rating: 5, comment: "Great!" })} label="Review ★5" />
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function Btn({ onClick, label, red }) {
  return (
    <button onClick={onClick} style={{
      padding:"4px 12px", background: red ? "#e74c3c" : "#3b82d4",
      color:"#fff", border:"none", borderRadius:5, cursor:"pointer", fontSize:12
    }}>{label}</button>
  );
}
