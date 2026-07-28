"use client";

/**
 * Escaneo de documentos por cámara (Sprint 38).
 *
 * Alcance real en navegador: los escáneres TWAIN/WIA no son accesibles
 * desde una página web por seguridad del navegador (requieren software
 * nativo). Lo que sí es viable y se implementa aquí es la CAPTURA POR
 * CÁMARA (getUserMedia) del computador o del móvil: se toman una o varias
 * páginas, se aplica una mejora de brillo/contraste sobre el canvas, y las
 * capturas se combinan en un ÚNICO PDF que se sube a la historia clínica
 * del paciente por el mismo endpoint de documentos.
 *
 * El recorte automático de bordes y la corrección de perspectiva exigen
 * visión por computador (OpenCV.js) — se deja como mejora futura; aquí se
 * ofrece encuadre manual y realce de imagen, que cubre el caso habitual.
 */

import { useEffect, useRef, useState } from "react";

import { apiBase } from "./api";

export default function DocumentScanner({ patientId, docType = "exam", onDone, onClose }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [pages, setPages] = useState([]);       // dataURLs mejoradas
  const [ready, setReady] = useState(false);
  const [enhance, setEnhance] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment" }, audio: false,
        });
        if (cancelled) { stream.getTracks().forEach((t) => t.stop()); return; }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
          setReady(true);
        }
      } catch {
        setError("No se pudo acceder a la cámara. Revisa los permisos del navegador.");
      }
    })();
    return () => {
      cancelled = true;
      if (streamRef.current) streamRef.current.getTracks().forEach((t) => t.stop());
    };
  }, []);

  function capture() {
    const video = videoRef.current;
    if (!video) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    if (enhance) {
      // Realce simple de brillo/contraste (documento más legible)
      const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const d = img.data;
      const contrast = 1.25, brightness = 12;
      for (let i = 0; i < d.length; i += 4) {
        for (let k = 0; k < 3; k++) {
          d[i + k] = Math.max(0, Math.min(255, (d[i + k] - 128) * contrast + 128 + brightness));
        }
      }
      ctx.putImageData(img, 0, 0);
    }
    setPages((p) => [...p, canvas.toDataURL("image/jpeg", 0.85)]);
  }

  function removePage(idx) {
    setPages((p) => p.filter((_, i) => i !== idx));
  }

  async function saveAsPdf() {
    if (pages.length === 0) { setError("Captura al menos una página."); return; }
    setSaving(true); setError("");
    try {
      const { jsPDF } = await import("jspdf");
      const pdf = new jsPDF({ unit: "px", format: "a4" });
      const pw = pdf.internal.pageSize.getWidth();
      const ph = pdf.internal.pageSize.getHeight();
      for (let i = 0; i < pages.length; i++) {
        if (i > 0) pdf.addPage();
        // Ajustar la imagen dentro de la página conservando proporción
        const img = new Image();
        img.src = pages[i];
        // eslint-disable-next-line no-await-in-loop
        await new Promise((res) => { img.onload = res; });
        const ratio = Math.min(pw / img.width, ph / img.height);
        const w = img.width * ratio, h = img.height * ratio;
        pdf.addImage(pages[i], "JPEG", (pw - w) / 2, (ph - h) / 2, w, h);
      }
      const blob = pdf.output("blob");

      // Subir por el mismo endpoint de documentos (a la historia clínica)
      const fd = new FormData();
      fd.append("doc_type", docType);
      fd.append("description", `Documento escaneado (${pages.length} pág.)`);
      fd.append("file", new File([blob], `escaneo_${Date.now()}.pdf`, { type: "application/pdf" }));
      const token = localStorage.getItem("access");
      const resp = await fetch(`${apiBase()}/api/v1/patients/${patientId}/documents/`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });
      if (!resp.ok) throw new Error(`No se pudo guardar (error ${resp.status}).`);
      onDone?.();
    } catch (err) {
      setError(err.message || "No se pudo generar el PDF.");
    } finally {
      setSaving(false);
    }
  }

  const btn = {
    background: "rgba(255,255,255,.14)", color: "#fff", border: "none",
    borderRadius: 8, padding: "8px 14px", cursor: "pointer", fontSize: 13,
  };

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 85, background: "rgba(15,23,42,.9)",
                  display: "flex", flexDirection: "column", color: "#fff" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 16px", flexWrap: "wrap" }}>
        <span style={{ fontWeight: 600, flex: 1 }}>Escanear documento (cámara)</span>
        <label style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}>
          <input type="checkbox" checked={enhance} onChange={(e) => setEnhance(e.target.checked)} />
          Mejorar brillo/contraste
        </label>
        <button style={{ ...btn, background: "rgba(255,255,255,.28)" }} onClick={onClose}>✕ Cerrar</button>
      </div>

      {error && <div style={{ background: "#7f1d1d", padding: "8px 16px", fontSize: 13 }}>{error}</div>}

      <div style={{ flex: 1, display: "flex", gap: 12, padding: 16, overflow: "hidden" }}>
        {/* Cámara */}
        <div style={{ flex: 2, display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
          <video ref={videoRef} playsInline muted
                 style={{ width: "100%", maxHeight: "70vh", background: "#000",
                          borderRadius: 10, objectFit: "contain" }} />
          <button style={{ ...btn, background: "var(--petrol)", color: "var(--on-brand)", padding: "10px 24px", fontSize: 15 }}
                  disabled={!ready} onClick={capture}>
            ◉ Capturar página
          </button>
        </div>

        {/* Páginas capturadas */}
        <div style={{ flex: 1, overflow: "auto", background: "rgba(255,255,255,.06)",
                      borderRadius: 10, padding: 12 }}>
          <div style={{ fontSize: 13, marginBottom: 8 }}>Páginas: {pages.length}</div>
          <div style={{ display: "grid", gap: 8 }}>
            {pages.map((p, i) => (
              <div key={i} style={{ position: "relative" }}>
                <img src={p} alt={`Página ${i + 1}`} style={{ width: "100%", borderRadius: 6 }} />
                <button onClick={() => removePage(i)}
                        style={{ position: "absolute", top: 4, right: 4, background: "rgba(0,0,0,.6)",
                                 color: "#fff", border: "none", borderRadius: 6, cursor: "pointer",
                                 padding: "2px 8px" }}>✕</button>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, padding: "12px 16px" }}>
        <button style={btn} onClick={onClose}>Cancelar</button>
        <button style={{ ...btn, background: "var(--petrol)", color: "var(--on-brand)" }} disabled={saving || pages.length === 0}
                onClick={saveAsPdf}>
          {saving ? "Guardando…" : `Guardar PDF (${pages.length} pág.)`}
        </button>
      </div>
    </div>
  );
}
