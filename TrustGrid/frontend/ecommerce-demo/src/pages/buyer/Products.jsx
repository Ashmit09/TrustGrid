import { useEffect, useState } from "react";
import { listProducts, placeOrder } from "../../api/client";

export default function Products() {
  const [products, setProducts] = useState([]);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    listProducts().then(r => setProducts(r.data)).catch(() => {});
  }, []);

  const handleBuy = async (productId) => {
    try {
      await placeOrder({ product_id: productId, quantity: 1 });
      setMsg("Order placed! Check Orders page.");
      setTimeout(() => setMsg(""), 3000);
    } catch (e) {
      setMsg(e.response?.data?.detail || "Failed to place order.");
    }
  };

  return (
    <div style={{ padding:"1.5rem" }}>
      <h2>Products</h2>
      {msg && <p style={{ color:"#27ae60" }}>{msg}</p>}
      {products.length === 0 && <p>No products yet.</p>}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(220px,1fr))", gap:16 }}>
        {products.map(p => (
          <div key={p.product_id} style={{ border:"1px solid #e5e7eb", borderRadius:8, padding:"1rem", background:"#fff" }}>
            <h4 style={{ margin:"0 0 4px" }}>{p.title}</h4>
            <p style={{ margin:"0 0 4px", color:"#57606a", fontSize:13 }}>{p.category}</p>
            <p style={{ margin:"0 0 12px", fontWeight:700, color:"#3b82d4" }}>₦{p.price}</p>
            <button onClick={() => handleBuy(p.product_id)}
              style={{ width:"100%", padding:"0.5rem", background:"#3b82d4", color:"#fff", border:"none", borderRadius:6, cursor:"pointer" }}>
              Buy Now
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
