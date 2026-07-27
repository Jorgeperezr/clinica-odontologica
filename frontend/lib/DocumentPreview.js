"use client";

/**
 * Vista previa de documentos en modal (Sprint 38).
 * Soporta PDF e imágenes (jpg/jpeg/png/gif/webp). Acciones: ampliar,
 * reducir, rotar (imágenes), descargar e imprimir. No abandona la página.
 *
 * El archivo se carga autenticado (api + blob) y se muestra desde un
 * objectURL, de modo que nunca se apunta a una URL con host interno.
 */

import { useEffect, useRef, useState } from "react";

import { api } from "./api";

const IMG_RE = /\.(png|jpe?g|gif|webp)$/i;
const PDF_RE = /\.pdf$/i;

export default function DocumentPreview({ doc, patientId, onClose, onDelete }) {
  const [blobUrl, setBlobUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const objectUrlRef = useRef(null);

  const name = doc?.file_name || doc?.description || "documento";
  const isImage = IMG_RE.test(name);
  const isPdf = PDF_RE.test(name);
  const fileEndpoint = `/patients/${patientId}/documents/${doc.id}/file/`;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true); setError("");
      try {
        const resp = await api(fileEndpoint);
        if (!resp.ok) throw new Error(`No se pudo cargar (error ${resp.status}).`);
        const blob = await resp.blob();
        if (cancelled) return;
        const url = URL.createObjectURL(blob);
        objectUrlRef.current = url;
        setBlobUrl(url);
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc.id, patientId]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function download() {
    try {
      const resp = await api(`${fileEndpoint}?download=1`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = name; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch { /* noop */ }
  }

  function printDoc() {
    if (!blobUrl) return;
    const w = window.open(blobUrl, "_blank");
    if (w) w.addEventListener("load", () => w.print());
  }

  const btn = {
    background: "rgba(255,255,255,.14)", color: "#fff", border: "none",
    borderRadius: 8, padding: "7px 12px", cursor: "pointer", fontSize: 13,
  };

  return (
    <div onClick={onClose}
         style={{ position: "fixed", inset: 0, zIndex: 80, background: "rgba(15,23,42,.82)",
                  display: "flex", flexDirection: "column" }}>
      {/* Barra de herramientas */}
      <div onClick={(e) => e.stopPropagation()}
           style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 16px",
                    color: "#fff", flexWrap: "wrap" }}>
        <span style={{ fontWeight: 600, fontSize: 14, flex: 1, overflow: "hidden",
                       textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{name}</span>
        {isImage && (
          <>
            <button style={btn} onClick={() => setZoom((z) => Math.max(0.25, z - 0.25))}>− Reducir</button>
            <button style={btn} onClick={() => setZoom((z) => Math.min(4, z + 0.25))}>+ Ampliar</button>
            <button style={btn} onClick={() => setRotation((r) => (r + 90) % 360)}>⟳ Rotar</button>
          </>
        )}
        <button style={btn} onClick={download}>⭳ Descargar</button>
        <button style={btn} onClick={printDoc}>⎙ Imprimir</button>
        {onDelete && (
          <button style={{ ...btn, background: "rgba(239,68,68,.35)" }} onClick={onDelete}>
            🗑 Eliminar
          </button>
        )}
        <button style={{ ...btn, background: "rgba(255,255,255,.28)" }} onClick={onClose}>✕ Cerrar</button>
      </div>

      {/* Lienzo */}
      <div onClick={(e) => e.stopPropagation()}
           style={{ flex: 1, overflow: "auto", display: "flex", alignItems: "center",
                    justifyContent: "center", padding: 16 }}>
        {loading && <div style={{ color: "#fff" }}>Cargando…</div>}
        {error && <div style={{ color: "#fca5a5" }}>{error}</div>}
        {!loading && !error && blobUrl && isImage && (
          <img src={blobUrl} alt={name}
               style={{ transform: `scale(${zoom}) rotate(${rotation}deg)`,
                        transition: "transform .15s ease", maxWidth: "90%", maxHeight: "100%",
                        boxShadow: "0 8px 40px rgba(0,0,0,.5)", background: "#fff" }} />
        )}
        {!loading && !error && blobUrl && isPdf && (
          <iframe title={name} src={blobUrl}
                  style={{ width: "92%", height: "100%", border: "none", borderRadius: 8, background: "#fff" }} />
        )}
        {!loading && !error && blobUrl && !isImage && !isPdf && (
          <div style={{ color: "#fff", textAlign: "center" }}>
            <p>Este tipo de archivo no tiene vista previa.</p>
            <button style={{ ...btn, marginTop: 10 }} onClick={download}>Descargar archivo</button>
          </div>
        )}
      </div>
    </div>
  );
}
