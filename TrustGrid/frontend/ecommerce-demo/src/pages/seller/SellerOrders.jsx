import { useEffect, useState } from "react";
import { listOrders, fulfillOrder, shipOrder, deliverOrder } from "../../api/client";

export default function SellerOrders() {
  const [orders, setOrders] = useState([]);
  const [msg, setMsg] = useState("");

  const load = () => listOrders().then(r => setOrders(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const action = async (fn, id) => {
    try { await fn(id); load(); setMsg("Updated!"); setTimeout(() => setMsg(""), 2000); }
    catch (e) { setMsg(e.response?.data?.detail || "Error"); }
  };

  return (
    <div style={{ padding:"1.5rem" }}>
      <h2>Incoming Orders</h2>
      {msg && <p style={{ color:"#27ae60" }}>{msg}</p>}
      {orders.length === 0 && <p>No orders yet.</p>}
      {orders.map(o => (
        <div key={o.order_id} style={{ border:"1px solid #e5e7eb", borderRadius:8, padding:"1rem", marginBottom:12, background:"#fff" }}>
          <div style={{ display:"flex", justifyContent:"space-between" }}>
            <strong>{o.order_id}</strong>
            <span style={{ fontSize:13, color:"#57606a" }}>{o.status}</span>
          </div>
          <p style={{ fontSize:13, color:"#57606a", margin:"4px 0 8px" }}>₦{o.total_amount}</p>
          <div style={{ display:"flex", gap:8 }}>
            {o.status === "PLACED"   && <Btn onClick={() => action(fulfillOrder, o.order_id)} label="Accept" />}
            {o.status === "ACCEPTED" && <Btn onClick={() => action(shipOrder, o.order_id)} label="Ship" />}
            {o.status === "SHIPPED"  && <Btn onClick={() => action(deliverOrder, o.order_id)} label="Mark Delivered" />}
          </div>
        </div>
      ))}
    </div>
  );
}

function Btn({ onClick, label }) {
  return <button onClick={onClick} style={{ padding:"4px 14px", background:"#3b82d4", color:"#fff", border:"none", borderRadius:5, cursor:"pointer", fontSize:12 }}>{label}</button>;
}
