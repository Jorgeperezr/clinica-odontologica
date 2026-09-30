# Logotipo de Clinube

El logotipo es el concepto «dos tonos»: `clinube` en minúsculas, «cli»
en el color de las letras y «nube» con el punto de la i en el de acento.
Está dibujado con trazados, no escrito con una tipografía, para que sea
idéntico en el panel, en la app y en los iconos.

| Dónde | Archivo |
|---|---|
| Panel (componentes `LogoClinube` e `IconoClinube`) | `frontend/lib/marca.js` |
| Favicon del panel | `frontend/app/icon.svg` |
| App (widgets `LogoClinube` e `IconoClinube`) | `movil/lib/logo.dart` |
| Iconos de la app (Android, iOS, web) | los genera `iconos.py` |

Los tres primeros llevan **las mismas cadenas de trazado**, copiadas a
mano. `django-api/apps/common/tests_marca.py` compara `marca.js`,
`logo.dart` e `icon.svg` y se pone rojo si se separan.

## Paleta

| | Claro | Oscuro |
|---|---|---|
| Letras («cli») | tinta `#0B1220` | blanco |
| Acento («nube» y el punto) | cian `#0E7490` | cian luz `#67E8F9` |
| «Sin color» | `#111111` + gris `#6B7280` | blanco + gris `#9CA3AF` |

Es el tema `default` de `frontend/lib/theme.js` y de
`django-api/apps/configuration/temas.py` (una prueba los mantiene
iguales): toda clínica nueva la tiene hasta que elige otra o sube su
logotipo. `sin_color` es el mismo logotipo en grises, como tema de la
clínica o como ajuste de cada persona.

## Regenerar los iconos de la app

Solo necesita Pillow, que ya está en el proyecto:

```sh
.venv/bin/python scripts/marca/iconos.py
```

## Volver a dibujar el logotipo

Hace falta solo si cambia la tipografía, el espaciado o la posición del
punto. `trazar.py` usa fontTools y uharfbuzz, que **no** son dependencias
del proyecto: se instalan en un entorno aparte y se tira después.

```sh
python3 -m venv /tmp/marca
/tmp/marca/bin/pip install fonttools uharfbuzz
```

La tipografía es DM Sans Bold con tamaño óptico 40 (licencia SIL OFL).
Google Fonts la entrega recortada a las letras que hacen falta: la
dirección del archivo `.ttf` sale de

```sh
curl -s "https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@40,700&text=clinube%C4%B1"
```

Con ese archivo descargado:

```sh
/tmp/marca/bin/python scripts/marca/trazar.py DMSans-opsz40-Bold.ttf > /tmp/logo.json
```

Las cadenas de `/tmp/logo.json` se copian en `marca.js`, `logo.dart` e
`icon.svg`; luego se regeneran los iconos y se pasan las pruebas.
