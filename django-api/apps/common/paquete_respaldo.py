"""
Lo que se descarga al generar una copia: un .zip con la copia cifrada y
lo necesario para abrirla SIN la plataforma.

    respaldo-….clinicabk   la copia (ver tenant_backup.py)
    COMO-DESCIFRAR.txt     instrucciones, con los datos de esta copia
    descifrar.html         herramienta para el navegador, sin internet
    descifrar.py           la misma para la terminal

Antes solo se podía abrir desde el propio panel. Si la clínica dejaba la
plataforma, o el panel no estaba disponible justo cuando hacía falta,
la copia era un archivo que nadie sabía leer: una copia que no se puede
abrir no es una copia. Las herramientas van dentro de cada descarga para
que viajen con ella, y el formato está descrito en las instrucciones
para que cualquier técnico pueda leerlo con otras herramientas.

Las herramientas están en `kit_respaldo/` y no dependen de nada de este
proyecto; `tests_paquete_respaldo.py` comprueba que abren las copias que
genera el servidor.
"""

import io
import zipfile
from pathlib import Path
from string import Template

from django.utils import timezone

from apps.common.tenant_backup import FILE_SUFFIX, BackupError

KIT = Path(__file__).resolve().parent / "kit_respaldo"
INSTRUCCIONES = "COMO-DESCIFRAR.txt"
HERRAMIENTAS = ("descifrar.html", "descifrar.py")


def _resumen(manifest):
    if manifest is None:
        return ("Instrucciones generales. Valen para cualquier copia .clinicabk\n"
                "generada desde el panel de la clínica.\n")
    alcance = manifest.get("alcance") or {"tipo": "clinica"}
    fecha = manifest.get("generated_at", "")
    try:
        from datetime import datetime

        fecha = timezone.localtime(datetime.fromisoformat(fecha)).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        # Una fecha que no se entiende se escribe tal cual: las
        # instrucciones siguen valiendo y la fecha exacta está en la copia.
        pass
    lineas = [f"  Clínica:       {manifest.get('tenant', {}).get('name', '')}",
              f"  Generada:      {fecha}",
              f"  Por:           {manifest.get('generated_by', {}).get('email', '')}"]
    if alcance.get("tipo") == "profesional":
        lineas.append(f"  Contenido:     pacientes de {alcance.get('full_name') or alcance.get('email')}"
                      f" ({alcance.get('pacientes', 0)}), su historia clínica y su agenda")
    else:
        lineas.append("  Contenido:     todos los datos de la clínica")
    lineas.append(f"  Registros:     {manifest.get('total_records', 0)}")
    return "\n".join(lineas) + "\n"


def instrucciones(manifest=None, archivo="respaldo.clinicabk"):
    plantilla = Template((KIT / INSTRUCCIONES).read_text(encoding="utf-8"))
    texto = plantilla.substitute(resumen=_resumen(manifest), archivo=archivo)
    # CRLF: el Bloc de notas antiguo de Windows no parte las líneas con LF.
    return texto.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")


def _con_herramientas(z, manifest, archivo):
    z.writestr(INSTRUCCIONES, instrucciones(manifest, archivo))
    for nombre in HERRAMIENTAS:
        z.write(KIT / nombre, nombre)


def empaquetar(blob, nombre_copia, manifest):
    """El .zip de la descarga: la copia + instrucciones + herramientas."""
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # La copia ya va comprimida y cifrada: comprimirla otra vez no
        # ahorra nada. Sin compresión además la lee descifrar.html en
        # cualquier navegador.
        z.writestr(zipfile.ZipInfo(nombre_copia, date_time=timezone.localtime().timetuple()[:6]),
                   blob, compress_type=zipfile.ZIP_STORED)
        _con_herramientas(z, manifest, nombre_copia)
    return salida.getvalue()


def solo_herramientas():
    """Las herramientas y las instrucciones, para quien las haya perdido."""
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", compression=zipfile.ZIP_DEFLATED) as z:
        _con_herramientas(z, None, "respaldo.clinicabk")
    return salida.getvalue()


def sacar_copia(datos):
    """
    Si lo subido es el .zip de la descarga, devuelve la copia de dentro;
    si no, lo devuelve tal cual. Así en el panel se puede elegir
    cualquiera de los dos.
    """
    if not datos.startswith(b"PK\x03\x04"):
        return datos
    try:
        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            dentro = [i for i in z.infolist() if i.filename.endswith(FILE_SUFFIX)]
            if len(dentro) != 1:
                raise BackupError("El .zip no contiene una copia .clinicabk.")
            return z.read(dentro[0])
    except zipfile.BadZipFile as exc:
        raise BackupError("El .zip está dañado.") from exc
