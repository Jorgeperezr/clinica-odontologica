"use client";

import { useState } from "react";

/**
 * Celdas de la matriz periodontal (Sprint 52).
 *
 * Componentes desacoplados: cada uno recibe su valor y un callback, sin
 * saber nada de la API ni del paciente. Reproducen los controles de la
 * ficha del proyecto de referencia (interruptor de presencia, casilla de
 * implante, selector de movilidad, marcadores de furcación, celdas de
 * sitio y campos numéricos), adaptados a los tokens del sistema.
 *
 * El realce por ESCALA en la celda activa viene de `.circle-nerve-clicked`
 * del proyecto original: crece a 1.35× además de cambiar de borde, lo que
 * se lee mejor a distancia que un simple cambio de color.
 */

/* Ancho de la columna de cada pieza. Eran 26 px, pero tres campos de
   sitio de 15 px no caben en 26 y se montaban unos sobre otros; y el
   periodontograma necesita espacio para dibujar la pieza con sus raíces
   y las líneas de margen y de bolsa encima. */
const CELL_W = 44;

/* Nombre de cada sitio de una cara, por su índice local (0, 1, 2). */
const SITIO = ["mesial", "central", "distal"];

/**
 * Orden en pantalla de los tres sitios de una cara. En los cuadrantes 1 y
 * 4 (mitad izquierda) mesial mira a la línea media, o sea a la DERECHA:
 * se ven distal, central, mesial. En el 2 y el 3, al revés. Antes se
 * mostraban siempre mesial-central-distal y en la mitad izquierda cada
 * valor quedaba en el lado contrario de la pieza.
 */
export function ordenSitios(code) {
  return ["1", "4"].includes(String(code)[0]) ? [2, 1, 0] : [0, 1, 2];
}

/** Interruptor de presencia de la pieza (su fila "Available"). */
export function PresenceSwitch({ on, onToggle, label }) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label}
            onClick={onToggle} title={on ? "Pieza presente" : "Pieza ausente"}
            style={{
              width: 30, height: 16, borderRadius: 999, border: "none",
              padding: 2, cursor: "pointer", display: "block", margin: "0 auto",
              background: on ? "var(--petrol)" : "var(--line-strong)",
              transition: "background var(--dur) var(--ease)",
            }}>
      <span aria-hidden="true"
            style={{
              display: "block", width: 12, height: 12, borderRadius: "50%",
              background: "#fff",
              transform: on ? "translateX(14px)" : "translateX(0)",
              transition: "transform var(--dur) var(--ease)",
            }} />
    </button>
  );
}

/** Casilla de implante. */
export function ImplantCheck({ on, onToggle, label, disabled }) {
  return (
    <input type="checkbox" checked={on} disabled={disabled}
           onChange={onToggle} aria-label={label}
           title="Implante"
           style={{ display: "block", margin: "0 auto", cursor: disabled ? "not-allowed" : "pointer",
                    accentColor: "var(--petrol)" }} />
  );
}

/** Selector de grado (movilidad 0-3). */
export function GradeSelect({ value, onChange, label, disabled, max = 3 }) {
  return (
    <select value={value} onChange={(e) => onChange(Number(e.target.value))}
            aria-label={label} disabled={disabled} title={label}
            style={{
              width: CELL_W + 8, fontSize: 10.5, padding: "1px 2px",
              textAlign: "center", borderRadius: 4,
              border: "1px solid var(--line)", background: "var(--elev)",
              color: "var(--ink)", cursor: disabled ? "not-allowed" : "pointer",
              display: "block", margin: "0 auto",
            }}>
      {Array.from({ length: max + 1 }, (_, i) => (
        <option key={i} value={i}>{i}</option>
      ))}
    </select>
  );
}

/**
 * Marcador de furcación. En el proyecto original se dibuja como un icono
 * relleno por grados (`.fork-icon1..3`); aquí se representa con un círculo
 * cuyo relleno crece con el grado.
 */
export function FurcationMark({ grade, onCycle, label, disabled }) {
  const fill = ["transparent", "35%", "70%", "100%"][Math.min(grade, 3)];
  return (
    <button type="button" onClick={onCycle} disabled={disabled}
            aria-label={`${label}: grado ${grade}`} title={`Furcación grado ${grade}`}
            style={{
              width: 14, height: 14, borderRadius: "50%", padding: 0,
              display: "block", margin: "0 auto", cursor: disabled ? "not-allowed" : "pointer",
              border: "1.5px solid var(--ink-soft)",
              background: grade === 0
                ? "var(--elev)"
                : `linear-gradient(90deg, var(--ink) ${fill}, var(--elev) ${fill})`,
              opacity: disabled ? 0.4 : 1,
              transition: "background var(--dur-fast) var(--ease)",
            }} />
  );
}

/** Celda booleana de sitio (placa o sangrado). Tres sitios por lado. */
export function SiteFlagRow({ values, base, color, onToggle, label, disabled, orden = [0, 1, 2] }) {
  return (
    <span style={{ display: "inline-flex", gap: 2, justifyContent: "center", width: "100%" }}>
      {orden.map((i) => {
        const idx = base + i;
        const on = Boolean(values?.[idx]);
        return (
          <button key={i} type="button" onClick={() => onToggle(idx)} disabled={disabled}
                  aria-pressed={on} aria-label={`${label}, ${SITIO[i]}`} title={SITIO[i]}
                  style={{
                    width: 11, height: 11, padding: 0,
                    background: on ? color : "var(--elev)",
                    border: "1px solid var(--line)", borderRadius: "50%",
                    cursor: disabled ? "not-allowed" : "pointer",
                    transition: "background var(--dur-fast) var(--ease)",
                  }} />
        );
      })}
    </span>
  );
}

/**
 * Campo de un sitio. Es de TEXTO y no `type="number"` por dos motivos
 * comprobados en el navegador:
 *
 *  · En Chromium el `number` mete sus flechas de incremento dentro de la
 *    caja; con 14 px de ancho tapaban la cifra y la ficha se veía vacía.
 *  · Un margen gingival negativo (hiperplasia) no se podía escribir: al
 *    teclear el «-» el valor aún no es un número, se convertía en 0 y
 *    el signo desaparecía. Aquí se guarda lo tecleado mientras se
 *    escribe y solo se envía cuando ya es un número válido.
 */
function CampoSitio({ valor, alerta, activo, negativos, disabled, etiqueta, titulo, onFocus, onValor }) {
  const [borrador, setBorrador] = useState(null);
  const patron = negativos ? /^-?\d{0,2}$/ : /^\d{0,2}$/;
  const alto = valor > alerta;
  return (
    <input type="text" inputMode={negativos ? "text" : "numeric"} disabled={disabled}
           value={borrador ?? String(valor)}
           onFocus={(e) => { onFocus?.(); e.target.select(); }}
           onBlur={() => setBorrador(null)}
           onChange={(e) => {
             const t = e.target.value.trim();
             if (!patron.test(t)) return;
             setBorrador(t);
             if (t !== "" && t !== "-") onValor(Number(t));
           }}
           aria-label={etiqueta} title={titulo}
           style={{
             width: 14, height: 16, padding: 0, textAlign: "center",
             fontSize: 10, borderRadius: 2,
             border: activo ? "1.5px solid var(--petrol)" : "1px solid var(--line)",
             background: alto ? "var(--red-soft)" : "var(--elev)",
             color: alto ? "var(--red)" : "var(--ink)",
             fontWeight: alto ? 700 : 400,
             transform: activo ? "scale(1.35)" : "scale(1)",
             zIndex: activo ? 2 : 1, position: "relative",
             transition: "transform var(--dur) var(--ease), background var(--dur-fast) var(--ease)",
           }} />
  );
}

/** Tres campos de sitio (sondaje o margen gingival) en el orden de la pantalla. */
export function SiteNumberRow({
  values, base, onChange, label, disabled, activeSite, onFocusSite,
  orden = [0, 1, 2], alerta = 4, negativos = false,
}) {
  return (
    <span style={{ display: "inline-flex", gap: 1, justifyContent: "center", width: "100%" }}>
      {orden.map((i) => {
        const idx = base + i;
        return (
          <CampoSitio key={i} valor={values?.[idx] ?? 0} alerta={alerta} negativos={negativos}
                      activo={activeSite === idx} disabled={disabled}
                      etiqueta={`${label}, ${SITIO[i]}`} titulo={SITIO[i]}
                      onFocus={() => onFocusSite?.(idx)}
                      onValor={(v) => onChange(idx, v)} />
        );
      })}
    </span>
  );
}

/** Celda de estado clínico por superficie (sincronizada con el odontograma). */
export function SurfaceStateCell({ code, surface, state, active, onSelect, surfaceLabel }) {
  return (
    <button type="button" role="gridcell" aria-selected={active}
            aria-label={`Pieza ${code}, ${surfaceLabel}${state ? `: ${state.label}` : ": sin registro"}`}
            title={`${surfaceLabel}${state ? ` · ${state.label}` : ""}`}
            onClick={() => onSelect(code, surface)}
            style={{
              width: CELL_W - 4, height: 14, padding: 0, display: "block", margin: "0 auto",
              background: state?.color || "var(--elev)",
              border: active ? "2px solid var(--petrol)" : "1px solid var(--line)",
              borderRadius: 3, cursor: "pointer",
              transform: active ? "scale(1.35)" : "scale(1)",
              zIndex: active ? 2 : 1, position: "relative",
              boxShadow: active ? "var(--shadow)" : "none",
              transition: "transform var(--dur) var(--ease), background var(--dur-fast) var(--ease)",
            }} />
  );
}

export { CELL_W };
