"use client";

/**
 * Pad de firma táctil (Sprint 22): canvas que captura la firma con el
 * dedo (móvil/tablet), stylus o mouse, usando Pointer Events (unifica
 * touch y mouse). Exporta PNG en base64 para el endpoint de firma de
 * consentimientos.
 */

import { useEffect, useRef, useState } from "react";

export default function SignaturePad({ onConfirm, onCancel }) {
  const canvasRef = useRef(null);
  const drawing = useRef(false);
  const [hasInk, setHasInk] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    // Escalar para pantallas retina (nitidez de la firma)
    const ratio = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * ratio;
    canvas.height = rect.height * ratio;
    const ctx = canvas.getContext("2d");
    ctx.scale(ratio, ratio);
    ctx.lineWidth = 2.2;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = "#16282b";
  }, []);

  function pos(e) {
    const rect = canvasRef.current.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }

  function start(e) {
    e.preventDefault();
    drawing.current = true;
    const ctx = canvasRef.current.getContext("2d");
    const { x, y } = pos(e);
    ctx.beginPath();
    ctx.moveTo(x, y);
    canvasRef.current.setPointerCapture(e.pointerId);
  }

  function move(e) {
    if (!drawing.current) return;
    e.preventDefault();
    const ctx = canvasRef.current.getContext("2d");
    const { x, y } = pos(e);
    ctx.lineTo(x, y);
    ctx.stroke();
    setHasInk(true);
  }

  function end() { drawing.current = false; }

  function clear() {
    const canvas = canvasRef.current;
    canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
    setHasInk(false);
  }

  function confirm() {
    onConfirm(canvasRef.current.toDataURL("image/png"));
  }

  return (
    <div style={overlay} role="dialog" aria-modal="true" aria-label="Firma del paciente">
      <div style={box}>
        <h3 style={{ marginBottom: 4 }}>Firma del paciente</h3>
        <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 10 }}>
          Firme dentro del recuadro con el dedo (pantalla táctil) o el mouse.
        </p>
        <canvas
          ref={canvasRef}
          onPointerDown={start} onPointerMove={move}
          onPointerUp={end} onPointerLeave={end}
          style={{
            width: "100%", height: 220, touchAction: "none",
            background: "#fff", border: "2px dashed var(--line)", borderRadius: 10,
            cursor: "crosshair",
          }}
        />
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 14 }}>
          <button className="btn btn-ghost" onClick={clear}>Borrar</button>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-ghost" onClick={onCancel}>Cancelar</button>
            <button className="btn btn-primary" disabled={!hasInk} onClick={confirm}>
              Confirmar firma
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

const overlay = {
  position: "fixed", inset: 0, background: "rgba(22,40,43,.5)",
  display: "flex", alignItems: "center", justifyContent: "center",
  zIndex: 100, padding: 16,
};
const box = {
  background: "var(--paper)", borderRadius: 14, padding: "20px 22px",
  maxWidth: 560, width: "100%", boxShadow: "0 18px 50px rgba(0,0,0,.25)",
};
