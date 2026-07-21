"use client";

/**
 * Vista previa y recorte del logotipo (Sprint 34).
 *
 * Muestra la imagen seleccionada al instante (antes de subirla), completa
 * y con su relación de aspecto. Sobre ella, un área de recorte que se
 * puede mover (arrastrando) y redimensionar (por la esquina inferior
 * derecha). "Usar imagen completa" salta el recorte; "Recortar y guardar"
 * genera un PNG solo con la zona elegida.
 */

import { useEffect, useRef, useState } from "react";

const BOX_W = 460;   // ancho máximo del lienzo de previsualización
const BOX_H = 300;   // alto máximo
const MIN_CROP = 24; // tamaño mínimo del área de recorte

export default function LogoCropper({ file, onConfirm, onCancel }) {
  const [imgUrl, setImgUrl] = useState(null);
  const [imgMeta, setImgMeta] = useState(null); // { natW, natH, dispW, dispH }
  const [crop, setCrop] = useState(null);       // { x, y, w, h } en px de pantalla
  const dragRef = useRef(null);                 // { mode: "move"|"resize", startX, startY, orig }
  const imgElRef = useRef(null);

  // Vista previa inmediata del archivo elegido
  useEffect(() => {
    if (!file) return;
    const url = URL.createObjectURL(file);
    setImgUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function handleImgLoad(e) {
    const natW = e.target.naturalWidth, natH = e.target.naturalHeight;
    const scale = Math.min(BOX_W / natW, BOX_H / natH, 1);
    const dispW = Math.round(natW * scale), dispH = Math.round(natH * scale);
    setImgMeta({ natW, natH, dispW, dispH });
    // Recorte inicial: 90% centrado
    const w = Math.round(dispW * 0.9), h = Math.round(dispH * 0.9);
    setCrop({ x: Math.round((dispW - w) / 2), y: Math.round((dispH - h) / 2), w, h });
  }

  // ── arrastre y redimensionado (pointer events: mouse y táctil) ──
  function startDrag(e, mode) {
    e.preventDefault();
    e.stopPropagation();
    dragRef.current = { mode, startX: e.clientX, startY: e.clientY, orig: { ...crop } };
    window.addEventListener("pointermove", onDrag);
    window.addEventListener("pointerup", endDrag);
  }
  function onDrag(e) {
    const d = dragRef.current;
    if (!d || !imgMeta) return;
    const dx = e.clientX - d.startX, dy = e.clientY - d.startY;
    setCrop(() => {
      let { x, y, w, h } = d.orig;
      if (d.mode === "move") {
        x = Math.max(0, Math.min(imgMeta.dispW - w, x + dx));
        y = Math.max(0, Math.min(imgMeta.dispH - h, y + dy));
      } else {
        w = Math.max(MIN_CROP, Math.min(imgMeta.dispW - x, w + dx));
        h = Math.max(MIN_CROP, Math.min(imgMeta.dispH - y, h + dy));
      }
      return { x, y, w, h };
    });
  }
  function endDrag() {
    dragRef.current = null;
    window.removeEventListener("pointermove", onDrag);
    window.removeEventListener("pointerup", endDrag);
  }

  // ── generación del recorte ──
  async function confirmCrop(useFull) {
    if (!imgMeta) return;
    if (useFull) { onConfirm(file); return; }
    const scale = imgMeta.natW / imgMeta.dispW;
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(crop.w * scale);
    canvas.height = Math.round(crop.h * scale);
    const ctx = canvas.getContext("2d");
    ctx.drawImage(
      imgElRef.current,
      Math.round(crop.x * scale), Math.round(crop.y * scale),
      canvas.width, canvas.height,
      0, 0, canvas.width, canvas.height,
    );
    canvas.toBlob((blob) => {
      if (!blob) { onConfirm(file); return; }
      const cropped = new File([blob], "logo.png", { type: "image/png" });
      onConfirm(cropped);
    }, "image/png");
  }

  if (!file) return null;

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 60, background: "rgba(15,23,42,.55)",
                  display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
      <div className="card" style={{ maxWidth: 560, width: "100%" }}>
        <h3 style={{ marginBottom: 4 }}>Ajustar logotipo</h3>
        <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 12 }}>
          Mueve el recuadro para elegir la zona, o arrastra la esquina inferior derecha
          para cambiar su tamaño. También puedes usar la imagen completa.
        </p>

        <div style={{ display: "flex", justifyContent: "center", marginBottom: 14 }}>
          <div style={{ position: "relative", lineHeight: 0,
                        width: imgMeta?.dispW, height: imgMeta?.dispH }}>
            {imgUrl && (
              <img ref={imgElRef} src={imgUrl} alt="Vista previa del logotipo"
                   onLoad={handleImgLoad}
                   style={{ width: imgMeta?.dispW || "auto", height: imgMeta?.dispH || "auto",
                            maxWidth: BOX_W, maxHeight: BOX_H, display: "block",
                            borderRadius: 8, border: "1px solid var(--line)" }} />
            )}
            {crop && (
              <div onPointerDown={(e) => startDrag(e, "move")}
                   style={{ position: "absolute", left: crop.x, top: crop.y,
                            width: crop.w, height: crop.h, cursor: "move",
                            border: "2px solid var(--petrol)", borderRadius: 4,
                            boxShadow: "0 0 0 9999px rgba(15,23,42,.35)", touchAction: "none" }}>
                <div onPointerDown={(e) => startDrag(e, "resize")}
                     style={{ position: "absolute", right: -8, bottom: -8, width: 18, height: 18,
                              borderRadius: "50%", background: "var(--petrol)", cursor: "nwse-resize",
                              border: "2px solid #fff", touchAction: "none" }} />
              </div>
            )}
          </div>
        </div>

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", flexWrap: "wrap" }}>
          <button className="btn btn-ghost" onClick={onCancel}>Cancelar</button>
          <button className="btn btn-ghost" onClick={() => confirmCrop(true)}>
            Usar imagen completa
          </button>
          <button className="btn btn-primary" onClick={() => confirmCrop(false)}>
            Recortar y guardar
          </button>
        </div>
      </div>
    </div>
  );
}
