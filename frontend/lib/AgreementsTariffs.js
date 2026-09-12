"use client";

/**
 * Configuración → Convenios y tarifarios (Sprint 71).
 * ────────────────────────────────────────────────────────────────────
 * El backend tenía `Agreement` y `Tariff` desde el Sprint 2 y no los leía
 * nadie: no había pantalla para cargarlos y el presupuesto se calculaba
 * siempre con el precio base del catálogo. Una clínica podía dar de alta
 * el convenio con una aseguradora y seguir cobrando la tarifa particular.
 *
 * La pantalla tiene dos mitades porque son dos trabajos distintos:
 *
 *   1. **Convenios** — alta y baja de aseguradoras/empresas, con su
 *      descuento porcentual opcional. Se hace una vez.
 *   2. **Rejilla de precios** — tratamiento × convenio. Es lo que se
 *      revisa de verdad, por columnas: «qué me paga esta aseguradora por
 *      cada cosa». Por eso es una tabla editable y no un formulario por
 *      tarifa.
 *
 * La rejilla muestra SIEMPRE un precio en cada celda, porque siempre hay
 * uno aplicable, pero distingue visualmente el precio **pactado** del
 * **heredado** (del tarifario general, del descuento del convenio o del
 * catálogo). Sin esa distinción la tabla se vería llena de cifras y nadie
 * sabría cuáles ha negociado de verdad. La herencia la resuelve el
 * servidor (`apps/configuration/pricing.py`), no esta pantalla: es una
 * regla de negocio y el presupuesto tiene que usar la misma.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "./api";

const money = (v) => `$${Number(v || 0).toFixed(2)}`;

/** Cómo se ha obtenido el precio de una celda. */
const SOURCE_HINT = {
  tariff: { label: "Pactado", title: "Precio cargado para este convenio." },
  discount: { label: "% convenio", title: "Calculado con el descuento del convenio." },
  general: { label: "General", title: "Heredado del tarifario general." },
  base: { label: "Catálogo", title: "Heredado del precio base del tratamiento." },
};

async function readError(resp) {
  const data = await resp.json().catch(() => ({}));
  const detail = data?.error?.details || data?.detail || data;
  const first = typeof detail === "object" ? Object.values(detail)[0] : detail;
  return Array.isArray(first) ? first[0] : String(first || `Error ${resp.status}`);
}

export default function AgreementsTariffs() {
  const [matrix, setMatrix] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const resp = await api("/config/price-matrix/");
      if (!resp.ok) throw new Error(await readError(resp));
      setMatrix(await resp.json());
    } catch (err) {
      setError(err.message || "No se pudo cargar el tarifario.");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      {error && <div className="error-box">{error}</div>}
      <AgreementsPanel onChanged={load} />
      {matrix === null
        ? <div className="empty">Cargando tarifario…</div>
        : <PriceGrid matrix={matrix} onReload={load} />}
    </div>
  );
}

/* ── 1. Convenios ─────────────────────────────────────────────────── */

function AgreementsPanel({ onChanged }) {
  const [agreements, setAgreements] = useState([]);
  const [form, setForm] = useState({ name: "", discount_percentage: "" });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const resp = await api("/config/agreements/");
      const data = await resp.json();
      setAgreements(data.results || data);
    } catch {
      setError("No se pudieron cargar los convenios.");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const body = { name: form.name };
      // Vacío ≠ 0: sin descuento el convenio solo aporta su tarifario, y un
      // 0 % guardado haría que la rejilla mostrara «% convenio» en celdas
      // que en realidad no descuentan nada.
      if (form.discount_percentage !== "") {
        body.discount_percentage = form.discount_percentage;
      }
      const resp = await api("/config/agreements/", {
        method: "POST", body: JSON.stringify(body),
      });
      if (!resp.ok) throw new Error(await readError(resp));
      setForm({ name: "", discount_percentage: "" });
      await load();
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(agreement) {
    setError("");
    try {
      const resp = await api(`/config/agreements/${agreement.id}/`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !agreement.is_active }),
      });
      if (!resp.ok) throw new Error(await readError(resp));
      await load();
      onChanged();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div style={{ marginBottom: 26 }}>
      <h3 style={{ marginBottom: 4 }}>Convenios</h3>
      <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 12, maxWidth: 640 }}>
        Aseguradoras y empresas con tarifas especiales. El descuento es opcional:
        sirve para el convenio de «un % a todo» y evita cargar una fila por
        tratamiento. Si además cargas un precio en la rejilla, ese precio manda.
      </p>

      {error && <div className="error-box">{error}</div>}

      <form onSubmit={submit} className="card" style={{ marginBottom: 14 }}>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr auto", gap: "0 12px", alignItems: "end" }}>
          <div className="field" style={{ marginBottom: 0 }}>
            <label htmlFor="conv-nombre">Nombre del convenio *</label>
            <input id="conv-nombre" required value={form.name}
                   placeholder="Aseguradora, empresa…"
                   onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label htmlFor="conv-desc">Descuento (%)</label>
            <input id="conv-desc" type="number" step="0.01" min="0" max="100"
                   placeholder="Opcional"
                   value={form.discount_percentage}
                   onChange={(e) => setForm({ ...form, discount_percentage: e.target.value })} />
          </div>
          <button className="btn btn-primary" disabled={saving}>
            {saving ? "Guardando…" : "Agregar"}
          </button>
        </div>
      </form>

      <div className="card" style={{ padding: 0 }}>
        {agreements.length === 0 ? (
          <div className="empty">Sin convenios. La clínica atiende solo a particulares.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Convenio</th><th>Descuento</th><th>Pacientes</th>
                <th>Estado</th><th aria-label="Acciones" />
              </tr>
            </thead>
            <tbody>
              {agreements.map((a) => (
                <tr key={a.id} style={{ opacity: a.is_active ? 1 : 0.55 }}>
                  <td style={{ fontWeight: 600 }}>{a.name}</td>
                  <td className="tabular">
                    {a.discount_percentage === null || a.discount_percentage === undefined
                      ? "—"
                      : `${Number(a.discount_percentage).toFixed(2)} %`}
                  </td>
                  <td className="tabular">{a.patient_count ?? 0}</td>
                  <td>
                    {a.is_active
                      ? <span className="badge badge-ok">Activo</span>
                      : <span className="badge badge-danger">Inactivo</span>}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button type="button" className="btn" onClick={() => toggleActive(a)}>
                      {a.is_active ? "Desactivar" : "Reactivar"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

/* ── 2. Rejilla de precios ────────────────────────────────────────── */

function PriceGrid({ matrix, onReload }) {
  const { agreements, treatments } = matrix;
  const [onlyActive, setOnlyActive] = useState(true);
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState(null);   // "<treatmentId>:<columnKey>"
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const columns = useMemo(
    () => (onlyActive ? agreements.filter((a) => a.is_active) : agreements),
    [agreements, onlyActive],
  );

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return treatments;
    return treatments.filter(
      (t) => t.name.toLowerCase().includes(needle)
          || (t.specialty_name || "").toLowerCase().includes(needle),
    );
  }, [treatments, query]);

  async function save(treatmentId, columnKey, rawValue) {
    // Enter dispara el guardado y, acto seguido, el desenfoque del input
    // dispara el suyo: sin este cerrojo salen dos PUT por cada celda.
    if (busy) return;
    const key = `${treatmentId}:${columnKey}`;
    setBusy(true);
    setError("");
    try {
      const resp = await api("/config/price-matrix/", {
        method: "PUT",
        body: JSON.stringify({
          treatment: treatmentId,
          agreement: columnKey === "general" ? null : columnKey,
          // Cadena vacía = borrar la fila y devolver la celda a su valor
          // heredado. Es la única forma de deshacer un precio pactado.
          price: rawValue === "" ? null : rawValue,
        }),
      });
      if (!resp.ok) throw new Error(await readError(resp));
      // Solo cierro la celda si sigue siendo la que se estaba editando:
      // al saltar de una celda a otra con un clic, el desenfoque guarda la
      // primera y cerrarla a ciegas apagaría la que acaba de abrirse.
      setEditing((actual) => (actual === key ? null : actual));
      await onReload();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function startEdit(treatment, columnKey) {
    const cell = treatment.prices[columnKey];
    setEditing(`${treatment.id}:${columnKey}`);
    // El borrador arranca vacío cuando el precio es heredado: si arrancara
    // con la cifra heredada, pulsar Enter sin tocar nada la convertiría en
    // un precio pactado sin que el usuario lo haya decidido.
    setDraft(cell.source === "tariff" ? cell.value : "");
  }

  return (
    <div>
      <h3 style={{ marginBottom: 4 }}>Rejilla de precios</h3>
      <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 12, maxWidth: 680 }}>
        Cada celda muestra el precio que se aplicará al presupuestar. Haz clic
        para fijar uno pactado; déjalo vacío y guarda para volver al heredado.
      </p>

      {error && <div className="error-box">{error}</div>}

      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", marginBottom: 12 }}>
        <input value={query} onChange={(e) => setQuery(e.target.value)}
               placeholder="Buscar tratamiento o especialidad…"
               aria-label="Buscar tratamiento"
               style={{ flex: "1 1 260px", maxWidth: 340, padding: "9px 12px",
                        border: "1px solid var(--line)", borderRadius: "var(--radius)" }} />
        <label style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 13 }}>
          <input type="checkbox" checked={onlyActive}
                 onChange={(e) => setOnlyActive(e.target.checked)} />
          Solo convenios activos
        </label>
      </div>

      <div className="card" style={{ padding: 0, overflowX: "auto" }}>
        {rows.length === 0 ? (
          <div className="empty">
            {treatments.length === 0
              ? "Sin tratamientos en el catálogo: cárgalos antes de fijar tarifas."
              : "Ningún tratamiento coincide con la búsqueda."}
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th style={{ minWidth: 200 }}>Tratamiento</th>
                <th style={{ minWidth: 110 }}>General</th>
                {columns.map((a) => (
                  <th key={a.id} style={{ minWidth: 110 }}>
                    {a.name}
                    {a.discount_percentage !== null && a.discount_percentage !== undefined && (
                      <span style={{ display: "block", fontWeight: 400, fontSize: 11,
                                     color: "var(--ink-soft)", textTransform: "none" }}>
                        −{Number(a.discount_percentage).toFixed(2)} %
                      </span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.id} style={{ opacity: t.is_active ? 1 : 0.55 }}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{t.name}</div>
                    <div style={{ fontSize: 12, color: "var(--ink-soft)" }}>{t.specialty_name}</div>
                  </td>
                  {["general", ...columns.map((a) => a.id)].map((columnKey) => {
                    const key = `${t.id}:${columnKey}`;
                    const cell = t.prices[columnKey];
                    if (!cell) return <td key={columnKey}>—</td>;
                    return (
                      <PriceCell
                        key={columnKey}
                        cell={cell}
                        editing={editing === key}
                        busy={busy}
                        draft={draft}
                        onDraft={setDraft}
                        onStart={() => startEdit(t, columnKey)}
                        onCancel={() => setEditing(null)}
                        onSave={() => save(t.id, columnKey, draft.trim())}
                        label={`${t.name} — ${columnKey === "general"
                          ? "tarifario general"
                          : (columns.find((a) => a.id === columnKey)?.name || "convenio")}`}
                      />
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function PriceCell({ cell, editing, busy, draft, onDraft, onStart, onCancel, onSave, label }) {
  const hint = SOURCE_HINT[cell.source] || SOURCE_HINT.base;
  const pactado = cell.source === "tariff";

  if (editing) {
    return (
      <td>
        <input
          autoFocus type="number" step="0.01" min="0" value={draft}
          aria-label={`Precio de ${label}`}
          placeholder="Heredado"
          disabled={busy}
          onChange={(e) => onDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") { e.preventDefault(); onSave(); }
            if (e.key === "Escape") { e.preventDefault(); onCancel(); }
          }}
          onBlur={onSave}
          style={{ width: 92, padding: "5px 7px", border: "1px solid var(--petrol)",
                   borderRadius: "var(--radius-sm, 4px)" }}
        />
      </td>
    );
  }

  return (
    <td>
      <button
        type="button"
        onClick={onStart}
        title={hint.title}
        aria-label={`Editar precio de ${label}. ${hint.title}`}
        style={{
          background: "transparent", border: "none", padding: "3px 0",
          textAlign: "left", cursor: "pointer", width: "100%",
        }}
      >
        <span className="tabular"
              style={{ fontWeight: pactado ? 700 : 400,
                       color: pactado ? "var(--ink)" : "var(--ink-soft)" }}>
          {money(cell.value)}
        </span>
        <span style={{ display: "block", fontSize: 11, color: "var(--ink-soft)" }}>
          {hint.label}
        </span>
      </button>
    </td>
  );
}
