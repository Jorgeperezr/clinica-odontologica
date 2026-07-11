"use client";

import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import SignaturePad from "../../../lib/SignaturePad";

export default function FirmaPage() {
  const [data, setData] = useState(null);
  const [license, setLicense] = useState("");
  const [drawing, setDrawing] = useState(false);
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");

  useEffect(() => {
    api("/doctors/me/signature/").then(async (r) => {
      const d = await r.json();
      if (r.ok) { setData(d); setLicense(d.license_number || ""); }
      else setError(d?.detail || "No se pudo cargar tu firma.");
    }).catch(() => setError("No se pudo cargar tu firma."));
  }, []);

  async function save(signatureDataURL) {
    setError(""); setOkMsg("");
    try {
      const body = { license_number: license };
      if (signatureDataURL) body.signature_image = signatureDataURL;
      const resp = await api("/doctors/me/signature/", {
        method: "POST", body: JSON.stringify(body),
      });
      const d = await resp.json();
      if (!resp.ok) throw new Error(d?.detail || `Error ${resp.status}`);
      if (signatureDataURL) {
        setData({ ...data, has_signature: true, signature_image: signatureDataURL });
      }
      setDrawing(false);
      setOkMsg("Guardado. Tu firma y registro se estampan en tus recetas.");
    } catch (err) { setError(err.message); }
  }

  return (
    <div style={{ maxWidth: 640 }}>
      <h1 style={{ fontSize: 24, marginBottom: 4 }}>Mi firma</h1>
      <p style={{ color: "var(--ink-soft)", marginBottom: 18, fontSize: 14 }}>
        Dibuja tu firma con el dedo (pantalla táctil) o el mouse. Se estampa
        automáticamente en tus recetas en PDF, junto a tu registro profesional.
        La firma electrónica legal (firmaEC) llegará como fase 2 con tu
        certificado .p12.
      </p>

      {error && <div className="error-box">{error}</div>}
      {okMsg && <div className="error-box" style={{ background: "var(--mint)", color: "var(--petrol-deep)" }}>✓ {okMsg}</div>}

      <div className="field" style={{ maxWidth: 320 }}>
        <label>Registro profesional (ej. MSP / ACESS)</label>
        <input value={license} onChange={(e) => setLicense(e.target.value)} placeholder="MSP-12345" />
      </div>

      {data?.has_signature && data.signature_image && !drawing && (
        <div className="card" style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 6 }}>Firma actual:</div>
          <img src={data.signature_image} alt="Firma actual"
               style={{ maxHeight: 80, background: "#fff", border: "1px solid var(--line)", borderRadius: 8, padding: 6 }} />
        </div>
      )}

      {drawing ? (
        <div className="card">
          <div style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 8 }}>
            Dibuja y presiona Confirmar:
          </div>
          <SignaturePad onConfirm={(sig) => save(sig)} onCancel={() => setDrawing(false)} />
        </div>
      ) : (
        <div style={{ display: "flex", gap: 10 }}>
          <button className="btn btn-primary" onClick={() => setDrawing(true)}>
            {data?.has_signature ? "Dibujar nueva firma" : "Dibujar mi firma"}
          </button>
          <button className="btn btn-ghost" onClick={() => save(null)}>
            Guardar solo el registro profesional
          </button>
        </div>
      )}
    </div>
  );
}
