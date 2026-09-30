/**
 * Identidad de la plataforma: Clinube.
 * ────────────────────────────────────────────────────────────────────
 * Dos marcas conviven en el panel y no hay que confundirlas:
 *
 *   - la de la CLÍNICA (su nombre, su logotipo y sus colores,
 *     `/config/branding/`), que es la que ve el personal y la que llevan
 *     los documentos del paciente;
 *   - la de la PLATAFORMA, Clinube, que aparece donde todavía no hay
 *     clínica (el acceso, el cambio de contraseña, la pestaña del
 *     navegador), en la barra lateral de una clínica que no ha subido
 *     su propio logotipo, y discreta al pie.
 *
 * El nombre no dice «dental» a propósito: la odontología es la primera
 * especialidad, no la única. Si algún día cambia, se cambia aquí y en
 * `django-api/config/settings.py` (MARCA).
 *
 * EL LOGOTIPO son trazados, no texto: «clinube» en DM Sans Bold (licencia
 * SIL OFL) convertida a contornos, con un espaciado de −0,035 em. Como
 * texto dependería de que la tipografía cargase y se vería distinto en
 * cada navegador; así es idéntico en el panel, en el favicon y en la
 * app (`movil/lib/logo.dart` usa las MISMAS cadenas, y el favicon
 * `app/icon.svg` la de la «c»; `apps/common/tests_marca.py` comprueba
 * que no se separen). «cli» va en el color de las letras; «nube» y el
 * punto de la i, en el de acento. La paleta —cian #0E7490 sobre tinta
 * #0B1220— está en PRESETS de lib/theme.js.
 *
 * Por omisión los colores salen de variables CSS (--ink y --logo-acento),
 * así que el logotipo sigue solo a la paleta: en «Sin color» se pinta en
 * grises y en todo lo demás sigue siendo el mismo.
 */

export const MARCA = "Clinube";
export const LEMA = "Gestión clínica en la nube";

export const TRAZOS = {
  cli: "M304 12Q227 12 168 -21.5Q109 -55 76 -113.5Q43 -172 43 -248Q43 -324 76.5 -382.5Q110 -441 169 -474.5Q228 -508 304 -508Q400 -508 466 -458Q532 -408 549 -320L407 -320Q398 -354 370 -373.5Q342 -393 303 -393Q268 -393 240.5 -376Q213 -359 197 -326.5Q181 -294 181 -248Q181 -214 190 -187.5Q199 -161 215.5 -142Q232 -123 254.5 -113Q277 -103 303 -103Q329 -103 350 -111.5Q371 -120 386 -136.5Q401 -153 407 -176L549 -176Q532 -90 466 -39Q400 12 304 12ZM617 0L617 -715L752 -715L752 0ZM836 0L836 -496L971 -496L971 0Z",
  nube: "M1053 0L1053 -496L1171 -496L1181 -413L1182 -413Q1206 -457 1248.5 -482.5Q1291 -508 1351 -508Q1413 -508 1456 -481.5Q1499 -455 1522 -404Q1545 -353 1545 -278L1545 0L1410 0L1410 -266Q1410 -328 1385 -361Q1360 -394 1306 -394Q1271 -394 1244.5 -377.5Q1218 -361 1203 -330.5Q1188 -300 1188 -256L1188 0ZM1806 12Q1745 12 1701.5 -14Q1658 -40 1635 -91.5Q1612 -143 1612 -218L1612 -496L1747 -496L1747 -230Q1747 -168 1772 -135Q1797 -102 1851 -102Q1886 -102 1912.5 -118.5Q1939 -135 1954 -165.5Q1969 -196 1969 -240L1969 -496L2104 -496L2104 0L1986 0L1976 -82L1975 -82Q1951 -39 1908.5 -13.5Q1866 12 1806 12ZM2488 12Q2450 12 2418.5 2Q2387 -8 2362.5 -26.5Q2338 -45 2320 -71L2319 -71L2306 0L2188 0L2188 -715L2323 -715L2323 -428Q2347 -460 2386.5 -484Q2426 -508 2487 -508Q2558 -508 2612.5 -474Q2667 -440 2698 -381.5Q2729 -323 2729 -247Q2729 -173 2698 -114Q2667 -55 2612.5 -21.5Q2558 12 2488 12ZM2456 -104Q2496 -104 2526.5 -122.5Q2557 -141 2574.5 -173.5Q2592 -206 2592 -248Q2592 -290 2574.5 -322.5Q2557 -355 2526.5 -373.5Q2496 -392 2456 -392Q2416 -392 2385 -373.5Q2354 -355 2336.5 -322.5Q2319 -290 2319 -248Q2319 -206 2336.5 -173.5Q2354 -141 2385 -122.5Q2416 -104 2456 -104ZM3039 12Q2963 12 2904.5 -20Q2846 -52 2813 -110Q2780 -168 2780 -243Q2780 -321 2812.5 -380.5Q2845 -440 2903.5 -474Q2962 -508 3040 -508Q3114 -508 3170.5 -476Q3227 -444 3258.5 -388.5Q3290 -333 3290 -263Q3290 -253 3290 -240.5Q3290 -228 3288 -215L2877 -215L2877 -298L3153 -298Q3150 -344 3118.5 -372Q3087 -400 3040 -400Q3005 -400 2976 -384.5Q2947 -369 2930 -337.5Q2913 -306 2913 -259L2913 -230Q2913 -190 2929 -160Q2945 -130 2973.5 -114Q3002 -98 3038 -98Q3075 -98 3100 -114.5Q3125 -131 3138 -157L3276 -157Q3261 -110 3228 -71.5Q3195 -33 3147 -10.5Q3099 12 3039 12Z",
  punto: { cx: 903.5, cy: -628, r: 90 },
  caja: [43, -718, 3247, 730],
};

export const TRAZOS_ICONO = {
  c: "M304 12Q227 12 168 -21.5Q109 -55 76 -113.5Q43 -172 43 -248Q43 -324 76.5 -382.5Q110 -441 169 -474.5Q228 -508 304 -508Q400 -508 466 -458Q532 -408 549 -320L407 -320Q398 -354 370 -373.5Q342 -393 303 -393Q268 -393 240.5 -376Q213 -359 197 -326.5Q181 -294 181 -248Q181 -214 190 -187.5Q199 -161 215.5 -142Q232 -123 254.5 -113Q277 -103 303 -103Q329 -103 350 -111.5Q371 -120 386 -136.5Q401 -153 407 -176L549 -176Q532 -90 466 -39Q400 12 304 12Z",
  punto: { cx: 667, cy: -612, r: 112 },
  caja: [43, -724, 736, 736],
};

/**
 * El logotipo completo. `alto` en píxeles; el ancho sale solo.
 * `tinta` pinta «cli»; `acento`, «nube» y el punto. Por omisión siguen
 * al tema (--ink y --petrol), así que en «Sin color» se vuelve gris sin
 * tocar nada más.
 */
export function LogoClinube({ alto = 28, tinta = "var(--ink)", acento = "var(--logo-acento)", titulo = MARCA }) {
  const [x, y, w, h] = TRAZOS.caja;
  const p = TRAZOS.punto;
  return (
    <svg height={alto} width={Math.round((alto * w) / h)} viewBox={`${x} ${y} ${w} ${h}`}
         role="img" aria-label={titulo} style={{ display: "block", flex: "none" }}>
      <path d={TRAZOS.cli} fill={tinta} />
      <path d={TRAZOS.nube} fill={acento} />
      <circle cx={p.cx} cy={p.cy} r={p.r} fill={acento} />
    </svg>
  );
}

/** La «c» con el punto: para espacios donde no cabe la palabra. */
export function IconoClinube({ alto = 24, tinta = "var(--ink)", acento = "var(--logo-acento)", titulo }) {
  const [x, y, w, h] = TRAZOS_ICONO.caja;
  const p = TRAZOS_ICONO.punto;
  return (
    <svg height={alto} width={Math.round((alto * w) / h)} viewBox={`${x} ${y} ${w} ${h}`}
         role={titulo ? "img" : undefined} aria-label={titulo} aria-hidden={titulo ? undefined : "true"}
         style={{ display: "block", flex: "none" }}>
      <path d={TRAZOS_ICONO.c} fill={tinta} />
      <circle cx={p.cx} cy={p.cy} r={p.r} fill={acento} />
    </svg>
  );
}
