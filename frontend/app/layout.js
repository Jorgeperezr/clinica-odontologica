import "./globals.css";

export const metadata = {
  title: "Clínica Odontológica",
  description: "Sistema de gestión para clínica odontológica",
};

export default function RootLayout({ children }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
