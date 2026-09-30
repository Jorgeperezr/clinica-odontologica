/**
 * Identidad de la plataforma: Clinube.
 * ────────────────────────────────────────────────────────────────────
 * Dos marcas conviven en el panel y no hay que confundirlas:
 *
 *   - la de la CLÍNICA (su nombre y su logotipo, `/config/branding/`),
 *     que es la que ve el personal en la barra lateral y la que llevan
 *     los documentos del paciente;
 *   - la de la PLATAFORMA, Clinube, que solo aparece donde todavía no
 *     hay clínica (el acceso, el cambio de contraseña, la pestaña del
 *     navegador) y, discreta, al pie de la barra lateral.
 *
 * El nombre no dice «dental» a propósito: la odontología es la primera
 * especialidad, no la única. Si algún día cambia, se cambia aquí y en
 * `django-api/config/settings.py` (MARCA).
 */

export const MARCA = "Clinube";
export const LEMA = "Gestión clínica en la nube";

/**
 * Símbolo de la marca: una nube con una cruz, dibujado en SVG para que
 * no dependa de ningún archivo ni de la tipografía. `color` es la nube
 * y `cruz` el trazo interior (el color del fondo sobre el que va).
 */
export function SimboloClinube({ size = 28, color = "currentColor", cruz = "#fff", titulo }) {
  return (
    <svg width={size} height={size * 0.8} viewBox="3 3 20 16" role={titulo ? "img" : undefined}
         aria-hidden={titulo ? undefined : "true"} aria-label={titulo}
         style={{ display: "block", flex: "none" }}>
      <g fill={color}>
        <circle cx="8.3" cy="14" r="4.3" />
        <circle cx="13.4" cy="10.2" r="5.6" />
        <circle cx="17.8" cy="14" r="4.3" />
        <rect x="8.3" y="12" width="9.5" height="6.3" />
      </g>
      <g fill={cruz}>
        <rect x="12.15" y="10.1" width="2.5" height="7" rx=".5" />
        <rect x="9.9" y="12.35" width="7" height="2.5" rx=".5" />
      </g>
    </svg>
  );
}
