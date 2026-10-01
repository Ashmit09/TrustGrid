import { useState } from "react";
import { createProduct } from "../../api/client";

export default function AddProduct() {
  const [form, setForm] = useState({ title:"", description:"", price:"", stock:"", category:"" });
  const [msg, setMsg] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await createProduct({ ...form, price: parseFloat(form.price), stock: parseInt(form.stock) });
      setMsg("Product listed!");
      setForm({ title:"", description:"", price:"", stock:"", category:"" });
    } catch (err) {
      setMsg(err.response?.data?.detail || "Failed.");
    }
  };

  return (
    <div style={{ padding:"1.5rem", maxWidth:480 }}>
      <h2>Add Product</h2>
      {msg && <p style={{ color:"#27ae60" }}>{msg}</p>}
      <form onSubmit={handleSubmit}>
        {[["title","Title"],["description","Description"],["price","Price (₦)"],
          ["stock","Stock Quantity"],["category","Category"]].map(([k,label]) => (
          <div key={k} style={{ marginBottom:12 }}>
            <label style={{ display:"block", fontSize:13, marginBottom:4 }}>{label}</label>
            <input style={{ width:"100%", padding:"0.5rem", border:"1px solid #e5e7eb", borderRadius:6, boxSizing:"border-box", fontSize:14 }}
              value={form[k]} onChange={e => setForm({...form, [k]: e.target.value})} required={k!=="description" && k!=="category"} />
          </div>
        ))}
        <button type="submit" style={{ padding:"0.6rem 1.5rem", background:"#3b82d4", color:"#fff", border:"none", borderRadius:6, cursor:"pointer" }}>
          List Product
        </button>
      </form>
    </div>
  );
}
