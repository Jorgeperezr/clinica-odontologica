import "./globals.css";

import { LEMA, MARCA } from "../lib/marca";

export const metadata = {
  title: MARCA,
  description: `${MARCA} — ${LEMA.toLowerCase()}`,
  applicationName: MARCA,
};

/**
 * Fija la apariencia antes del primer pintado.
 * Sin esto la página se dibuja en claro y salta a oscuro cuando React
 * arranca: un parpadeo breve pero muy visible. El script es mínimo y
 * síncrono a propósito, para ejecutarse antes de que el navegador
 * pinte el primer fotograma.
 */
const noFlashTheme = `
(function () {
  try {
    var m = localStorage.getItem("colorMode") || "system";
    var dark = m === "dark" || (m === "system" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  } catch (e) {}
})();
`;

export default function RootLayout({ children }) {
  return (
    <html lang="es" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: noFlashTheme }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
