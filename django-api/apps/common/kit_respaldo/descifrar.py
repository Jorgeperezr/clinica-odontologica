#!/usr/bin/env python3
"""
Descifra una copia de seguridad de la clínica (.clinicabk) sin la
plataforma.

Uso:
    python3 descifrar.py respaldo.clinicabk
    python3 descifrar.py respaldo.clinicabk --csv carpeta
    python3 descifrar.py respaldo.zip

Pide la frase sin mostrarla en pantalla (o la lee de la variable de
entorno FRASE_RESPALDO, para automatizarlo) y escribe al lado del
archivo un .json con todo el contenido. Con --csv deja además un CSV
por tabla, separado por punto y coma, que Excel abre directamente.

Necesita Python 3.8+ y la biblioteca «cryptography»:
    python3 -m pip install cryptography

El formato está descrito en COMO-DESCIFRAR.txt. Este programa no se
conecta a nada: todo ocurre en este equipo.
"""

import argparse
import csv
import getpass
import gzip
import json
import os
import struct
import sys
import zipfile

MAGIC = b"CLINICABK"
CABECERA = ">9sBI"
TAM_CABECERA = struct.calcsize(CABECERA)
SAL, NONCE, ETIQUETA = 16, 12, 16


def fallar(mensaje):
    print(f"Error: {mensaje}", file=sys.stderr)
    sys.exit(1)


def leer_copia(ruta):
    """Bytes de la copia, desde el .clinicabk o desde el .zip que la trae."""
    if zipfile.is_zipfile(ruta):
        with zipfile.ZipFile(ruta) as z:
            dentro = [n for n in z.namelist() if n.endswith(".clinicabk")]
            if len(dentro) != 1:
                fallar("el .zip no contiene exactamente una copia .clinicabk.")
            return z.read(dentro[0])
    with open(ruta, "rb") as f:
        return f.read()


def descifrar(blob, frase):
    try:
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    except ImportError:
        fallar("falta la biblioteca «cryptography». Instálala con:\n"
               "    python3 -m pip install cryptography")

    if len(blob) < TAM_CABECERA + SAL + NONCE + ETIQUETA:
        fallar("el archivo no es una copia de seguridad válida.")
    cabecera = blob[:TAM_CABECERA]
    magia, version, iteraciones = struct.unpack(CABECERA, cabecera)
    if magia != MAGIC:
        fallar("el archivo no es una copia de seguridad de la clínica.")
    if version != 1:
        fallar(f"la copia usa el formato v{version} y este programa lee el v1.")
    if not 1_000 <= iteraciones <= 5_000_000:
        fallar("el archivo tiene una cabecera inconsistente.")

    sal = blob[TAM_CABECERA:TAM_CABECERA + SAL]
    nonce = blob[TAM_CABECERA + SAL:TAM_CABECERA + SAL + NONCE]
    cifrado = blob[TAM_CABECERA + SAL + NONCE:]
    clave = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=sal,
                       iterations=iteraciones).derive(frase.encode("utf-8"))
    try:
        comprimido = AESGCM(clave).decrypt(nonce, cifrado, cabecera)
    except InvalidTag:
        fallar("la frase no es la correcta o el archivo está dañado.")
    return json.loads(gzip.decompress(comprimido).decode("utf-8"))


# Primero lo que una persona busca; identificadores y fechas técnicas, al final.
PRIMERO = ["first_name", "last_name", "full_name", "name", "national_id", "patient", "date",
           "scheduled_start", "type", "notes", "allergies", "medications", "conditions"]
AL_FINAL = ["tenant", "created_at", "updated_at", "deleted_at"]


def orden(campo):
    if campo in PRIMERO:
        return (0, PRIMERO.index(campo), campo)
    return (2 if campo in AL_FINAL else 1, 0, campo)


def celda(valor):
    if isinstance(valor, (dict, list)):
        return json.dumps(valor, ensure_ascii=False)
    return "" if valor is None else valor


def escribir_csv(contenido, carpeta):
    os.makedirs(carpeta, exist_ok=True)
    tablas = {}
    for r in contenido.get("records", []):
        tablas.setdefault(r["model"], []).append(r)
    for modelo, filas in sorted(tablas.items()):
        campos = sorted({c for f in filas for c in f["fields"]}, key=orden)
        ruta = os.path.join(carpeta, f"{modelo}.csv")
        # utf-8-sig y punto y coma: así lo abre Excel en español sin
        # pasar por el asistente de importación.
        with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["id"] + campos)
            for fila in filas:
                w.writerow([fila["pk"]] + [celda(fila["fields"].get(c)) for c in campos])
    return len(tablas)


def main():
    p = argparse.ArgumentParser(description="Descifra una copia de seguridad de la clínica.")
    p.add_argument("archivo", help="el .clinicabk (o el .zip que lo trae)")
    p.add_argument("--csv", metavar="CARPETA", help="además, un CSV por tabla en esta carpeta")
    p.add_argument("--salida", metavar="ARCHIVO", help="dónde escribir el JSON")
    args = p.parse_args()

    if not os.path.exists(args.archivo):
        fallar(f"no existe {args.archivo}")
    blob = leer_copia(args.archivo)
    frase = os.environ.get("FRASE_RESPALDO") or getpass.getpass("Frase de cifrado: ")
    contenido = descifrar(blob, frase.strip())

    m = contenido.get("manifest", {})
    salida = args.salida or os.path.splitext(args.archivo)[0] + ".json"
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(contenido, f, ensure_ascii=False, indent=1)

    print(f"Copia de «{m.get('tenant', {}).get('name', '?')}» del {m.get('generated_at', '?')[:16]}")
    alcance = m.get("alcance") or {}
    if alcance.get("tipo") == "profesional":
        print(f"Pacientes de {alcance.get('full_name') or alcance.get('email')}: {alcance.get('pacientes')}")
    print(f"{m.get('total_records', 0)} registros → {salida}")
    if args.csv:
        print(f"{escribir_csv(contenido, args.csv)} tablas en CSV → {args.csv}/")
    print("El resultado está SIN CIFRAR y contiene datos de salud: bórralo al terminar.")


if __name__ == "__main__":
    main()
