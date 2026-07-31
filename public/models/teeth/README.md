# Mallas dentales externas (opcional)

El odontograma 3D funciona sin nada en esta carpeta: en ese caso usa la
geometría procedural, que no descarga nada y no arrastra licencias.

Para sustituirla por mallas anatómicas profesionales **no hay que tocar
código**. Basta con dejar aquí los ficheros y un `manifest.json`; el
odontograma los detecta al abrir la pestaña y los usa automáticamente.

## Marco local que deben cumplir las mallas

    +X  mesio-distal   → a lo largo de la arcada
    +Z  vestibular     → hacia fuera de la boca
    +Y  oclusal        → corona hacia arriba
    origen             → en el cuello (unión amelocementaria)

Solo hace falta preparar las piezas del **cuadrante superior derecho y
del inferior derecho** (11-18 y 41-48): el sistema refleja y reutiliza.
Si se aportan todas, mejor. Cada pieza que falte la cubre la procedural,
así que un juego incompleto nunca deja huecos en la arcada.

## manifest.json

```json
{
  "transform": { "rotation": [0, 0, 0], "scale": 0.1, "offset": [0, 0, 0] },
  "teeth": {
    "11": "incisivo-central-superior.glb",
    "16": { "file": "molares-superiores.glb", "node": "Molar_16",
            "transform": { "rotation": [0, 90, 0], "cervixY": 4.2 } }
  }
}
```

- `transform` en la raíz se aplica a todas las piezas; el de cada pieza
  lo completa o lo sobrescribe. Sirve para corregir la orientación y la
  escala con las que venga el modelo, sin reexportarlo.
- `scale` puede ser un número o `[x, y, z]`. La escena trabaja a razón de
  **1 unidad ≈ 10,7 mm**, así que un modelo en milímetros suele necesitar
  `"scale": 0.093`.
- `cervixY` indica la altura del cuello en las coordenadas del fichero.
  Si se omite, se estima por la constricción de la pieza.
- `node` selecciona una malla concreta cuando el fichero trae varias.
- `draco: { "decoderPath": "/models/teeth/draco/" }` activa la
  descompresión Draco si los ficheros vienen comprimidos.

## Formatos

`.glb` (recomendado, un solo fichero) o `.gltf`. Conviene decimar a
~3.000-6.000 triángulos por pieza: por encima de eso no se aprecia
diferencia a la escala a la que se ve una arcada completa, y sí se nota
en tablet.

## Licencias

Verificar la licencia antes de incorporar nada. Las fuentes anatómicas
abiertas más habituales (BodyParts3D, Z-Anatomy) están bajo CC BY-SA,
que obliga a compartir las obras derivadas en las mismas condiciones —
una decisión que hay que tomar de forma consciente en un producto
comercial. Esta carpeta se deja vacía a propósito.
