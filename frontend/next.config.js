/** @type {import('next').NextConfig} */

/**
 * La configuración se exporta como FUNCIÓN para poder mirar la fase en la
 * que Next arranca. Hace falta por un motivo concreto y caro de
 * diagnosticar:
 *
 * `next dev` y `next build` escribían los dos en `.next`. Como la
 * validación obligatoria de cada cambio incluye `next build`, lanzarla
 * con el servidor de desarrollo en marcha —lo normal mientras se prueba
 * algo— le pisaba el directorio por debajo. El panel seguía respondiendo,
 * pero con la compilación equivocada: `NEXT_PUBLIC_API_URL` llegaba
 * vacía y el login moría con «Failed to fetch», sin una sola petición en
 * la pestaña de red. Otro mensaje que no se parece en nada a su causa.
 *
 * El apaño se limita A PROPÓSITO a la compilación de validación:
 *
 *   · desarrollo        → .next
 *   · validación        → .next-build   (no estorba al servidor en marcha)
 *   · exportación       → .next  y  out/
 *
 * La exportación se deja EXACTAMENTE como estaba porque no es un detalle
 * interno: `docker-compose.prod.yml` copia el sitio desde `out/`, y al
 * cambiarle el directorio ese `out/` dejaba de crearse. La compilación
 * seguía diciendo que todo fue bien y el despliegue habría servido un
 * directorio vacío. Comprobado antes de subirlo: con la configuración
 * anterior salen 14 páginas en `out/`; con el directorio cambiado, cero.
 *
 * Y no hay riesgo de choque en ese caso: la exportación la ejecutan el CI
 * y el despliegue, donde no hay ningún servidor de desarrollo en marcha.
 */
const ESTATICO = process.env.NEXT_EXPORT === "1";

module.exports = (phase) => ({
  output: ESTATICO ? "export" : undefined,
  trailingSlash: true,
  distDir:
    phase === "phase-development-server" || ESTATICO ? ".next" : ".next-build",
});
