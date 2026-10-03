"""
Copia de seguridad cifrada de UNA clínica (Sprint 65).
────────────────────────────────────────────────────────────────────────
La administradora de la clínica genera desde su panel un archivo cifrado
con todos los datos de SU clínica, y desde el mismo panel puede
descifrarlo para consultar la información.

QUÉ NO ES ESTO
`scripts/backup.sh` vuelca la base ENTERA con pg_dump: es la copia de
recuperación de la plataforma, la ejecuta quien administra el servidor y
contiene los datos de todas las clínicas. Este módulo es otra cosa: la
copia que se lleva una clínica de sus propios datos. Por eso está
acotado al tenant y por eso el Super Administrador no puede emitirla —
no es titular de esos datos, y ampliar el alcance convertiría la función
en una vía para sacar información de clínicas ajenas.

FORMATO DEL ARCHIVO

    b"CLINICABK" | versión (1B) | iteraciones (4B, big-endian)
                 | sal (16B)    | nonce (12B) | AES-256-GCM(...)

La cabecera va como datos autenticados asociados (AAD), de modo que
alterar la versión o las iteraciones invalida el descifrado en lugar de
degradarlo en silencio. La clave sale de PBKDF2-HMAC-SHA256 sobre la
frase que escribe la administradora; esa frase no se guarda en ninguna
parte, así que si se pierde, el archivo es irrecuperable. Ese es
justamente el objetivo del cifrado y hay que decírselo en pantalla.

El contenido, ya descifrado, es JSON con un manifiesto y los registros
en formato de fixture de Django, para que un técnico pueda releerlos con
`loaddata` sin herramientas propias.
"""

import gzip
import json
import os
import struct
import unicodedata
from datetime import datetime

from django.apps import apps
from django.core import serializers
from django.utils import timezone

MAGIC = b"CLINICABK"
VERSION = 1
KDF_ITERATIONS = 400_000
SALT_BYTES = 16
NONCE_BYTES = 12
HEADER_STRUCT = ">9sBI"                     # magic, versión, iteraciones
HEADER_SIZE = struct.calcsize(HEADER_STRUCT)

FILE_SUFFIX = ".clinicabk"

# Tablas que NO entran en la copia de una clínica.
EXCLUDED_MODELS = {
    # Datos de la plataforma, no de la clínica.
    "common.PlatformConfiguration",
    "common.Tenant",                # se guarda aparte, en el manifiesto
    # Catálogo compartido por todas las clínicas.
    "clinical.Cie10",
    # Credenciales y material de un solo uso: incluirlos en un archivo
    # que sale del servidor sería regalar vectores de acceso, y no son
    # información clínica ni administrativa que a nadie le sirva.
    "accounts.OTPCode",
    "accounts.PasswordResetToken",
    "accounts.DeviceToken",
}

# Campos que se vacían antes de escribir. El hash de la contraseña es
# suficiente para montar un ataque de diccionario sin límite de intentos.
REDACTED_FIELDS = {
    "accounts.User": ("password",),
    # Cifrado con la clave del servidor, pero sigue siendo una credencial
    # de Meta: no tiene nada que hacer en un archivo que sale de él.
    "whatsapp.ConfiguracionWhatsApp": ("access_token_cifrado",),
}


class BackupError(Exception):
    """Error previsto al generar o leer una copia (frase incorrecta, etc.)."""


# ── Cifrado ───────────────────────────────────────────────────────────
def _derive_key(passphrase, salt, iterations):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt(payload: bytes, passphrase: str) -> bytes:
    """Cifra `payload` con la frase dada y devuelve el archivo completo."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt = os.urandom(SALT_BYTES)
    nonce = os.urandom(NONCE_BYTES)
    header = struct.pack(HEADER_STRUCT, MAGIC, VERSION, KDF_ITERATIONS)
    key = _derive_key(passphrase, salt, KDF_ITERATIONS)
    blob = AESGCM(key).encrypt(nonce, payload, header)
    return header + salt + nonce + blob


def decrypt(blob: bytes, passphrase: str) -> bytes:
    """
    Descifra un archivo generado por `encrypt`. Lanza BackupError si la
    frase no es la correcta o si el archivo se alteró: AES-GCM no
    distingue un caso del otro, y tampoco conviene distinguirlos.
    """
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if len(blob) < HEADER_SIZE + SALT_BYTES + NONCE_BYTES + 16:
        raise BackupError("El archivo no es una copia de seguridad válida.")

    header = blob[:HEADER_SIZE]
    try:
        magic, version, iterations = struct.unpack(HEADER_STRUCT, header)
    except struct.error as exc:
        raise BackupError("El archivo no es una copia de seguridad válida.") from exc
    if magic != MAGIC:
        raise BackupError("El archivo no es una copia de seguridad de la clínica.")
    if version != VERSION:
        raise BackupError(f"La copia usa el formato v{version} y este sistema lee el v{VERSION}.")
    if not 1_000 <= iterations <= 5_000_000:
        raise BackupError("El archivo tiene una cabecera inconsistente.")

    salt = blob[HEADER_SIZE:HEADER_SIZE + SALT_BYTES]
    nonce = blob[HEADER_SIZE + SALT_BYTES:HEADER_SIZE + SALT_BYTES + NONCE_BYTES]
    ciphertext = blob[HEADER_SIZE + SALT_BYTES + NONCE_BYTES:]

    key = _derive_key(passphrase, salt, iterations)
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, header)
    except InvalidTag as exc:
        raise BackupError(
            "No se pudo descifrar: la frase de cifrado no coincide o el archivo está dañado."
        ) from exc


# ── Recolección de datos ──────────────────────────────────────────────
_DOMAIN_APPS = (
    "accounts.", "agenda.", "app_paciente.", "billing.", "clinical.", "common.",
    "configuration.", "inventory.", "logros.", "patients.", "specialties.", "whatsapp.",
)


def _tenant_path(model, seen=None):
    """
    Ruta de filtrado desde `model` hasta el tenant, o None si no la hay.

    Muchas tablas hijas no llevan tenant propio (un ítem de presupuesto
    pertenece al presupuesto, y este a la clínica). Resolver la ruta
    recorriendo las claves foráneas evita mantener a mano una lista que
    se quedaría desactualizada en cuanto alguien añada un modelo.

    Se prueban primero las relaciones obligatorias: filtrar por una
    opcional dejaría fuera de la copia, sin avisar, las filas que la
    tengan vacía.
    """
    if any(f.name == "tenant" for f in model._meta.fields):
        return "tenant"

    seen = seen or set()
    label = model._meta.label
    if label in seen:
        return None
    seen = seen | {label}

    relations = [f for f in model._meta.fields if f.is_relation and f.related_model is not None]
    for field in sorted(relations, key=lambda f: bool(f.null)):
        sub = _tenant_path(field.related_model, seen)
        if sub:
            return f"{field.name}__{sub}"
    return None


def _exportable_models():
    """Modelos del dominio que entran en la copia, con su ruta al tenant."""
    out = []
    for model in apps.get_models():
        label = model._meta.label
        if label in EXCLUDED_MODELS or not label.startswith(_DOMAIN_APPS):
            continue
        path = _tenant_path(model)
        if path:
            out.append((label, model, path))
    return sorted(out, key=lambda item: item[0])


def _serializar(label, qs):
    rows = json.loads(serializers.serialize("json", qs.order_by("pk").iterator(chunk_size=500)))
    for row in rows:
        for field in REDACTED_FIELDS.get(label, ()):
            row["fields"].pop(field, None)
    return rows


def _manifiesto(tenant, requested_by, records, counts, alcance):
    return {
        "format": "clinica-backup",
        "version": VERSION,
        "generated_at": timezone.now().isoformat(),
        "tenant": {"id": str(tenant.id), "name": tenant.name, "ruc": tenant.ruc},
        "generated_by": {
            "id": str(getattr(requested_by, "id", "") or ""),
            "email": getattr(requested_by, "email", "") or "",
            "full_name": getattr(requested_by, "full_name", "") or "",
        },
        "alcance": alcance,
        "total_records": len(records),
        "counts": counts,
        "excluded_models": sorted(EXCLUDED_MODELS),
        "redacted_fields": {k: list(v) for k, v in REDACTED_FIELDS.items()},
        "notes": (
            "Los archivos adjuntos (radiografías, documentos escaneados, "
            "logotipo) no van dentro: la copia guarda su ruta, no su contenido."
        ),
    }


def collect(tenant, requested_by=None):
    """
    Reúne los datos de la clínica en una estructura JSON-serializable.

    Los registros van en formato de fixture de Django para que la copia
    sea legible y recargable con herramientas estándar.
    """
    records = []
    counts = {}
    for label, model, path in _exportable_models():
        rows = _serializar(label, model._default_manager.filter(**{path: tenant}))
        if rows:
            counts[label] = len(rows)
            records.extend(rows)
    manifest = _manifiesto(tenant, requested_by, records, counts, {"tipo": "clinica"})
    return {"manifest": manifest, "records": records}


# ── Copia de un profesional ───────────────────────────────────────────
# Qué es «la información que tiene» un doctor o un auxiliar: los
# pacientes que ha atendido —con cita suya o con algo que él escribió en
# su historia— y, de esos, la historia clínica completa, que es lo que ve
# en el panel y lo que necesita para seguir atendiéndolos. De la clínica
# se lleva su propia agenda y los catálogos que dan nombre a lo que hay
# en la historia (tratamientos, especialidades, estados del odontograma).
#
# Lo que NO lleva: cobros, inventario, auditoría, usuarios del resto del
# personal, citas de otros profesionales ni pacientes que no ha tocado.
# Es una lista cerrada a propósito: un modelo nuevo no entra en la copia
# de un profesional hasta que alguien decida aquí que debe entrar.

# Dónde deja rastro un profesional en la historia de un paciente:
# (modelo, campo que apunta al Doctor, campo que apunta al User).
_HUELLAS = (
    ("agenda.Appointment", "doctor", None),
    ("clinical.Evolution", "doctor", "created_by"),
    ("clinical.Form033Record", "doctor", "created_by"),
    ("clinical.Diagnosis", "doctor", None),
    ("clinical.ToothRecord", "doctor", None),
    ("clinical.TreatmentPlan", "created_by", None),
    ("clinical.PeriodontalExam", None, "created_by"),
    ("clinical.ExamRequest", None, "requested_by"),
    ("clinical.RadiographPhoto", None, "uploaded_by"),
    ("clinical.InformedConsent", None, "created_by"),
    ("specialties.SpecialtyForm", "doctor", None),
)

# Historia de sus pacientes: (modelo, ruta hasta el paciente).
_DE_SUS_PACIENTES = (
    ("patients.Patient", "pk"),
    ("patients.MedicalBackground", "patient"),
    ("patients.PatientDocument", "patient"),
    ("clinical.ClinicalRecord", "patient"),
    ("clinical.Diagnosis", "patient"),
    ("clinical.Evolution", "patient"),
    ("clinical.ExamRequest", "patient"),
    ("clinical.Form033Record", "patient"),
    ("clinical.InformedConsent", "patient"),
    ("clinical.PeriodontalExam", "patient"),
    ("clinical.PeriodontalTooth", "exam__patient"),
    ("clinical.RadiographPhoto", "patient"),
    ("clinical.ToothRecord", "patient"),
    ("clinical.TreatmentPlan", "patient"),
    ("clinical.TreatmentPlanItem", "treatment_plan__patient"),
    ("specialties.SpecialtyForm", "patient"),
)

# Catálogos de la clínica que dan nombre a lo que aparece en la historia.
_CATALOGOS = ("clinical.OdontogramState", "configuration.Treatment", "specialties.Specialty")


def pacientes_del_profesional(tenant, usuario):
    """Ids de los pacientes en cuya historia ha dejado rastro esta persona."""
    from django.db.models import Q

    from apps.agenda.models import Doctor

    doctor = Doctor.objects.filter(tenant=tenant, user=usuario).first()
    ids = set()
    for label, campo_doctor, campo_usuario in _HUELLAS:
        condicion = Q()
        if campo_doctor and doctor:
            condicion |= Q(**{campo_doctor: doctor})
        if campo_usuario:
            condicion |= Q(**{campo_usuario: usuario})
        if not condicion:
            continue
        model = apps.get_model(label)
        ids.update(model._default_manager.filter(condicion, tenant=tenant)
                   .values_list("patient_id", flat=True))
    ids.discard(None)
    return ids, doctor


def collect_profesional(tenant, usuario):
    """Copia de UN profesional: sus pacientes, su agenda y su ficha."""
    pacientes, doctor = pacientes_del_profesional(tenant, usuario)
    conjuntos = [(label, {f"{ruta}__in" if ruta != "pk" else "pk__in": pacientes})
                 for label, ruta in _DE_SUS_PACIENTES]
    conjuntos += [(label, {}) for label in _CATALOGOS]
    conjuntos += [("accounts.User", {"pk": usuario.pk})]
    if doctor:
        conjuntos += [("agenda.Doctor", {"pk": doctor.pk}), ("agenda.Appointment", {"doctor": doctor})]

    records, counts = [], {}
    for label, filtro in sorted(conjuntos, key=lambda c: c[0]):
        model = apps.get_model(label)
        path = _tenant_path(model)
        rows = _serializar(label, model._default_manager.filter(**{path: tenant}, **filtro))
        if rows:
            counts[label] = counts.get(label, 0) + len(rows)
            records.extend(rows)
    alcance = {"tipo": "profesional", "user_id": str(usuario.pk),
               "full_name": usuario.full_name or "", "email": usuario.email,
               "pacientes": len(pacientes)}
    manifest = _manifiesto(tenant, usuario, records, counts, alcance)
    return {"manifest": manifest, "records": records}


def build_encrypted(tenant, passphrase, requested_by=None, profesional=None):
    """
    Copia comprimida y cifrada. Devuelve (bytes, manifiesto).

    Sin `profesional`, la de toda la clínica; con él, solo lo suyo.
    """
    payload = (collect_profesional(tenant, profesional) if profesional is not None
               else collect(tenant, requested_by=requested_by))
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return encrypt(gzip.compress(raw, compresslevel=6), passphrase), payload["manifest"]


def read_encrypted(blob, passphrase):
    """Descifra y devuelve el contenido de una copia. Lanza BackupError si falla."""
    try:
        raw = gzip.decompress(decrypt(blob, passphrase))
    except BackupError:
        raise
    except Exception as exc:      # gzip corrupto pese a autenticar
        raise BackupError("La copia se descifró pero su contenido está dañado.") from exc

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupError("La copia no contiene datos legibles.") from exc

    if not isinstance(payload, dict) or payload.get("manifest", {}).get("format") != "clinica-backup":
        raise BackupError("El archivo no es una copia de seguridad de la clínica.")
    return payload


def _slug(texto, largo=40):
    ascii_name = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    slug = "".join(ch if ch.isalnum() else "-" for ch in ascii_name)
    return "-".join(part for part in slug.lower().split("-") if part)[:largo]


def suggested_filename(tenant, profesional=None):
    """
    Nombre de archivo sugerido, en ASCII. La cabecera Content-Disposition
    viaja en latin-1 y no todos los navegadores manejan bien una tilde
    ahí, así que «Clínica» se convierte en «clinica» antes de escribirlo.
    La copia de un profesional lleva su nombre, para no confundirla con
    la de la clínica.
    """
    slug = _slug(tenant.name) or "clinica"
    if profesional is not None:
        quien = _slug(profesional.full_name or profesional.email.split("@")[0], 30)
        slug = f"{slug}-{quien}" if quien else slug
    return f"respaldo-{slug}-{datetime.now():%Y-%m-%d_%H%M}{FILE_SUFFIX}"
