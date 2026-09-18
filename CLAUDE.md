# Convenciones del proyecto

Notas para cualquier sesión que trabaje en este repositorio. Están aquí
porque el entorno de desarrollo remoto es efímero: lo que no esté
escrito en el repositorio se pierde al arrancar el siguiente contenedor.

## Autoría de los commits

Antes del primer commit de la sesión:

```sh
git config user.name  "Jorgeperezr"
git config user.email "148003448+Jorgeperezr@users.noreply.github.com"
```

No es cosmético. GitHub solo cuenta un commit en el gráfico de
contribuciones si el **correo del autor** está ligado a la cuenta; con
el valor por defecto del entorno remoto —`Claude
<noreply@anthropic.com>`— el trabajo de este repositorio no aparecía en
el perfil de su dueño. Se usa la dirección `users.noreply` de GitHub y no
la personal: cuenta igual y no publica un correo privado en la historia.

Los mensajes de commit siguen llevando su línea `Co-Authored-By:`.

## Validar como valida el CI, no como sea más cómodo

```sh
python manage.py test --settings=config.settings_test
```

`python manage.py test` a secas usa `config.settings`: PostgreSQL y el
hasher real, unos 265 segundos. El CI usa `config.settings_test`: SQLite
en memoria y MD5, unos once. **La diferencia no es solo de velocidad.**
El cupo de peticiones anónimas (20/min por IP) vive en la caché y se
comparte entre pruebas: en once segundos la suite entera cae dentro de
una misma ventana de un minuto y el cupo se agota; en 265 segundos la
ventana se renueva varias veces y el problema no se ve. Una suite puede
estar verde en local y roja en el CI por esto solo.

El CI hace además una segunda pasada con `DJANGO_TIME_ZONE=Pacific/Kiritimati`
(UTC+14), para que la fecha del servidor y la de la clínica no coincidan
nunca. Varios fallos de frontera de fecha han salido de ahí.

Antes de subir: los tests con los settings del CI, `ruff check apps
config` y, si se tocó el panel, `npx next build`.

## Archivos que no se tocan

El odontograma está fuera de alcance salvo permiso explícito:

- `frontend/lib/odontogram/meshProvider.js`
- `frontend/lib/odontogram/contract.js`
- `frontend/lib/odontogram/registry.js`
- `frontend/lib/odontogram/Odontogram3D.js`
- `frontend/lib/ClinicalTabs.js`
- `frontend/lib/Odontogram.js` (clásico) y
  `frontend/lib/periodontal/PeriodontalMatrix.js`

Tampoco se tocan la lógica clínica, la sincronización entre
odontogramas, el raycasting, la historia ni los tratamientos. La
canalización GLTF/GLB debe seguir operativa: dejar mallas en
`public/models/teeth` tiene que bastar para sustituir la geometría
procedural, y el sistema de lóbulos de desarrollo se mantiene.

## Otras reglas en vigor

- **Sin dependencias nuevas.** Cambios incrementales, sin regresiones y
  con tiempos de generación parecidos.
- **El formulario MSP/MCP (HCU-033/2021) conserva su propio diseño** y no
  usa el motor de estilos de documentos.
- **Las copias de seguridad son del administrador de la clínica**, no del
  superadministrador de la plataforma.

## Idioma

Código, comentarios, mensajes de commit y textos de interfaz en
castellano, como el resto del repositorio.
