"use client";

/**
 * Imagen servida por un endpoint autenticado (Sprint 66).
 * ────────────────────────────────────────────────────────────────────
 * Las radiografías y los documentos de pacientes ya no se sirven desde
 * /media/: los entrega la API, que valida clínica, paciente y permisos
 * antes de devolver el binario. Una etiqueta <img src> no puede llevar
 * la cabecera Authorization, así que el archivo se pide con fetch y se
 * pinta desde un objectURL, igual que hace `DocumentPreview` con el
 * documento a tamaño completo.
 *
 * El objectURL se libera al desmontar y al cambiar de archivo: son
 * referencias en memoria del navegador y una rejilla de miniaturas las
 * acumularía sin descanso.
 */

import { useEffect, useRef, useState } from "react";

import { api } from "./api";

export default function AuthImage({ path, alt = "", style, fallback = null }) {
  const [url, setUrl] = useState(null);
  const [failed, setFailed] = useState(false);
  const objectUrl = useRef(null);

  useEffect(() => {
    let cancelled = false;

    function release() {
      if (objectUrl.current) {
        URL.revokeObjectURL(objectUrl.current);
        objectUrl.current = null;
      }
    }

    setUrl(null);
    setFailed(false);
    if (!path) return undefined;

    (async () => {
      try {
        // `api()` antepone /api/v1; el endpoint llega con ese prefijo.
        const resp = await api(path.replace(/^\/api\/v1/, ""));
        if (!resp.ok) throw new Error(`Error ${resp.status}`);
        const blob = await resp.blob();
        if (cancelled) return;
        release();
        objectUrl.current = URL.createObjectURL(blob);
        setUrl(objectUrl.current);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();

    return () => { cancelled = true; release(); };
  }, [path]);

  if (failed || (!url && fallback === null)) {
    return <div style={{ ...style, background: "var(--petrol-soft)" }} aria-hidden="true" />;
  }
  if (!url) return fallback;
  return <img src={url} alt={alt} style={style} />;
}
