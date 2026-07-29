"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../../../lib/api";
import BackButton from "../../../lib/BackButton";

const money = (v) => Number(v || 0).toFixed(2);

export default function InventarioPage() {
  const [products, setProducts] = useState([]);
  const [expiring, setExpiring] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [batchFor, setBatchFor] = useState(null); // producto al que se agrega lote
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [pResp, eResp] = await Promise.all([
        api("/products/"),
        api("/inventory/alerts/expiring/?days=30"),
      ]);
      const p = await pResp.json();
      setProducts(p.results || p);
      const e = await eResp.json();
      setExpiring(e.expiring_batches || []);
    } catch { setError("No se pudo cargar el inventario."); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const lowCount = products.filter((p) => p.is_low_stock).length;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <BackButton fallback="/panel/" />
        <h1 style={{ fontSize: 24 }}>Inventario</h1>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cerrar" : "+ Nuevo producto"}
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}

      {/* Alertas */}
      {(lowCount > 0 || expiring.length > 0) && (
        <div style={{ display: "flex", gap: 12, marginBottom: 18, flexWrap: "wrap" }}>
          {lowCount > 0 && (
            <div className="error-box" style={{ flex: 1, minWidth: 220, marginBottom: 0 }}>
              ⚠ {lowCount} producto{lowCount > 1 ? "s" : ""} con stock bajo
            </div>
          )}
          {expiring.length > 0 && (
            <div className="error-box" style={{ flex: 1, minWidth: 220, marginBottom: 0,
                 background: "var(--amber-soft)", color: "var(--amber)" }}>
              ⏳ {expiring.length} lote{expiring.length > 1 ? "s" : ""} vence{expiring.length > 1 ? "n" : ""} en 30 días
            </div>
          )}
        </div>
      )}

      {showForm && <ProductForm onSaved={() => { setShowForm(false); load(); }} />}
      {batchFor && (
        <BatchForm product={batchFor}
                   onClose={() => setBatchFor(null)}
                   onSaved={() => { setBatchFor(null); load(); }} />
      )}

      <div className="card" style={{ padding: 0 }}>
        {products.length === 0 ? (
          <div className="empty">Sin productos. Registra el primero.</div>
        ) : (
          <table>
            <thead>
              <tr><th>Producto</th><th>Unidad</th><th>Stock</th><th>Mínimo</th><th>Estado</th><th></th></tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.id}>
                  <td style={{ fontWeight: 600 }}>{p.name}</td>
                  <td>{p.unit}</td>
                  <td className="tabular">{money(p.current_stock)}</td>
                  <td className="tabular">{money(p.min_stock)}</td>
                  <td>
                    {p.is_low_stock
                      ? <span className="badge badge-danger">Stock bajo</span>
                      : <span className="badge badge-ok">OK</span>}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button className="btn btn-ghost" style={{ padding: "4px 12px", fontSize: 12 }}
                            onClick={() => setBatchFor(p)}>+ Lote</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Lotes por vencer */}
      {expiring.length > 0 && (
        <div className="card" style={{ padding: 0, marginTop: 18 }}>
          <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--line)", fontWeight: 600 }}>
            Lotes próximos a vencer (30 días)
          </div>
          <table>
            <thead><tr><th>Producto</th><th>Lote</th><th>Cantidad</th><th>Vence</th><th>Días</th></tr></thead>
            <tbody>
              {expiring.map((b) => (
                <tr key={b.batch_id}>
                  <td>{b.product_name}</td>
                  <td className="tabular">{b.batch_number}</td>
                  <td className="tabular">{money(b.quantity)}</td>
                  <td className="tabular">{b.expiration_date}</td>
                  <td className="tabular" style={{ color: b.days_to_expiry <= 7 ? "var(--red)" : "var(--amber)", fontWeight: 600 }}>
                    {b.days_to_expiry}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ProductForm({ onSaved }) {
  const [form, setForm] = useState({ name: "", unit: "unidad", min_stock: "0" });
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const resp = await api("/products/", { method: "POST", body: JSON.stringify(form) });
      if (!resp.ok) throw new Error(`No se pudo crear el producto (error ${resp.status}).`);
      onSaved();
    } catch (err) { setError(err.message); }
  }

  return (
    <form onSubmit={submit} className="card" style={{ marginBottom: 18 }}>
      <h3 style={{ marginBottom: 12 }}>Nuevo producto</h3>
      {error && <div className="error-box">{error}</div>}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: "0 14px" }}>
        <div className="field"><label>Nombre *</label>
          <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
        <div className="field"><label>Unidad</label>
          <input value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} /></div>
        <div className="field"><label>Stock mínimo</label>
          <input type="number" step="0.01" value={form.min_stock}
                 onChange={(e) => setForm({ ...form, min_stock: e.target.value })} /></div>
      </div>
      <button className="btn btn-primary">Guardar producto</button>
    </form>
  );
}

function BatchForm({ product, onClose, onSaved }) {
  const [form, setForm] = useState({ batch_number: "", quantity: "", expiration_date: "" });
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const body = { ...form, product: product.id };
      if (!body.expiration_date) delete body.expiration_date;
      const resp = await api(`/products/${product.id}/batches/`, {
        method: "POST", body: JSON.stringify(body),
      });
      if (!resp.ok) throw new Error(`No se pudo registrar el lote (error ${resp.status}).`);
      onSaved();
    } catch (err) { setError(err.message); }
  }

  return (
    <form onSubmit={submit} className="card" style={{ marginBottom: 18, borderColor: "var(--petrol)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
        <h3>Nuevo lote — {product.name}</h3>
        <button type="button" className="btn btn-ghost" style={{ padding: "4px 12px", fontSize: 12 }} onClick={onClose}>✕</button>
      </div>
      {error && <div className="error-box">{error}</div>}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0 14px" }}>
        <div className="field"><label>Nº de lote *</label>
          <input required value={form.batch_number}
                 onChange={(e) => setForm({ ...form, batch_number: e.target.value })} /></div>
        <div className="field"><label>Cantidad *</label>
          <input type="number" step="0.01" required value={form.quantity}
                 onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></div>
        <div className="field"><label>Vencimiento</label>
          <input type="date" value={form.expiration_date}
                 onChange={(e) => setForm({ ...form, expiration_date: e.target.value })} /></div>
      </div>
      <button className="btn btn-primary">Registrar lote (entrada)</button>
    </form>
  );
}
