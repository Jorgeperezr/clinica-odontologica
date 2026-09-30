"""
Alertas clínicas a partir de los antecedentes del paciente.

Dos usos:

  · alertas_de_antecedentes(): lo que hay que tener presente con ESTE
    paciente antes de tocarlo (alergias, anticoagulantes, bifosfonatos,
    embarazo…). Se enseña arriba de su ficha.
  · revisar_receta(): cruza el texto de una receta con esas alertas y
    avisa si receta algo que choca (amoxicilina a un alérgico a la
    penicilina, un AINE a un anticoagulado…).

Principios, porque esto es seguridad del paciente:

  1. **Avisa, no bloquea.** La decisión es del profesional; una regla
     no conoce el caso. Por eso cada alerta dice qué texto de los
     antecedentes la disparó: el doctor puede ver que «penicilina»
     venía de «alergia a la penicilina en la infancia, dudosa» y
     decidir.
  2. **Sin IA ni servicios externos.** Son reglas explícitas y
     revisables sobre texto normalizado (minúsculas, sin tildes),
     escritas aquí y probadas en tests_alertas.py.
  3. **Las negaciones no disparan.** «Niega alergias», «sin alergia a
     la penicilina» o «no toma anticoagulantes» no deben avisar de lo
     contrario. Se trocea el texto por frases y se descarta la que
     empieza negando. Es una heurística: por eso la cita de la fuente.

Esto es una ayuda, no una guía clínica: las reglas cubren las
interacciones más comunes en odontología general y deben revisarse con
el criterio de la clínica.
"""

import re
import unicodedata

ALTO, MEDIO = "alto", "medio"


def normalizar(texto):
    t = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


_NEGACION = re.compile(r"^\s*(niega|no\b|sin\b|ningun|ninguna|descarta|negativo|nada)")


def _fragmentos(texto):
    """Frases del campo, sin las que empiezan negando."""
    for trozo in re.split(r"[.;,\n]+", texto or ""):
        if trozo.strip() and not _NEGACION.match(normalizar(trozo)):
            yield trozo.strip()


def _buscar(texto, raices):
    """(raíz encontrada, frase original) de la primera coincidencia, o None."""
    for frase in _fragmentos(texto):
        n = normalizar(frase)
        for raiz in raices:
            if re.search(r"\b" + re.escape(raiz), n):
                return raiz, frase
    return None


# ── Vocabulario ────────────────────────────────────────────────────────
PENICILINAS = ["penicilin", "amoxicilin", "ampicilin", "augmentin", "betalactam", "dicloxacilin"]
CEFALOSPORINAS = ["cefalexin", "cefadroxil", "cefuroxim", "ceftriaxon", "cefazolin", "cefalosporin"]
OTROS_ANTIBIOTICOS = ["clindamicin", "azitromicin", "eritromicin", "claritromicin", "metronidazol",
                      "doxiciclin", "tetraciclin", "minociclin", "ciprofloxacin", "levofloxacin"]
TETRACICLINAS = ["doxiciclin", "tetraciclin", "minociclin"]
AINE = ["ibuprofen", "naproxen", "diclofenac", "ketorolac", "aspirin", "acido acetilsalicilico",
        "ketoprofen", "dexketoprofen", "meloxicam", "celecoxib", "etoricoxib", "nimesulid",
        "piroxicam", "aine"]
ANESTESICOS = ["lidocain", "articain", "mepivacain", "prilocain", "bupivacain", "anestesi"]
ANTICOAGULANTES = ["warfarin", "acenocumarol", "sintrom", "rivaroxaban", "xarelto", "apixaban",
                   "eliquis", "dabigatran", "pradaxa", "edoxaban", "heparin", "enoxaparin",
                   "clopidogrel", "plavix", "ticagrelor", "prasugrel", "anticoagul", "antiagreg"]
BIFOSFONATOS = ["alendron", "risedron", "ibandron", "zoledron", "pamidron", "bifosfonat",
                "denosumab", "prolia", "xgeva", "fosamax"]
DIABETES = ["diabet", "metformin", "insulin", "glibenclamid"]
CARDIOVASCULAR = ["hipertens", "cardiopat", "infarto", "arritmia", "angina", "insuficiencia cardiaca",
                  "enf. cardiaca", "enfermedad cardiaca"]
ENDOCARDITIS = ["endocarditis", "protesis valvular", "valvula protesica", "valvula artificial",
                "cardiopatia congenita"]
HEMORRAGICOS = ["hemofilia", "hemorrag", "coagulopat", "von willebrand", "trombocitopen"]


def _antecedentes_033(form033):
    """
    Casillas marcadas en el último formulario 033 (sección D), con su
    detalle escrito, y el embarazo. {nombre de casilla: detalle}.
    """
    if form033 is None:
        return {}, None
    marcadas = {k: (v.get("detail") or "") for k, v in (form033.antecedentes_personales or {}).items()
                if isinstance(v, dict) and v.get("checked")}
    return marcadas, form033.embarazada


def alertas_de_antecedentes(fondo, form033=None):
    """
    Alertas del paciente a partir de sus antecedentes (MedicalBackground)
    y del último formulario 033: las casillas marcadas y lo que se
    escribió en su detalle («Alergia antibiótico: amoxicilina»).

    Devuelve una lista de dicts: clave, nivel, titulo, detalle, fuente.
    """
    alergias = getattr(fondo, "allergies", "") if fondo else ""
    medicacion = getattr(fondo, "medications", "") if fondo else ""
    condiciones = getattr(fondo, "conditions", "") if fondo else ""
    embarazada = getattr(fondo, "is_pregnant", None) if fondo else None
    marcadas, embarazada_033 = _antecedentes_033(form033)

    salida = []

    def agregar(clave, nivel, titulo, detalle, fuente):
        salida.append({"clave": clave, "nivel": nivel, "titulo": titulo,
                       "detalle": detalle, "fuente": fuente})

    def de_texto(campo_nombre, texto, raices):
        hallado = _buscar(texto, raices)
        return f"{campo_nombre}: «{hallado[1]}»" if hallado else None

    def de_033(casillas, raices):
        """El detalle escrito en alguna de esas casillas marcadas."""
        for casilla in casillas:
            if casilla in marcadas and (f := de_texto(f"Formulario 033 ({casilla})", marcadas[casilla], raices)):
                return f
        return None

    def casilla(nombre):
        return f"Formulario 033: «{nombre}»" if nombre in marcadas else None

    # Dónde puede estar escrita una alergia, una enfermedad o un fármaco.
    def en_alergias(raices):
        return de_texto("Alergias", alergias, raices) or de_033(
            ("Alergia antibiótico", "Alergia anestesia", "Otro"), raices)

    def en_condiciones(raices):
        return de_texto("Condiciones", condiciones, raices) or de_033(("Otro",), raices)

    def en_medicacion(raices):
        return de_texto("Medicación", medicacion, raices) or de_033(("Otro",), raices)

    if f := en_alergias(PENICILINAS):
        agregar("alergia_penicilina", ALTO, "Alergia a penicilinas",
                "No recetar penicilinas (amoxicilina, ampicilina…). Precaución con cefalosporinas.", f)
    elif f := casilla("Alergia antibiótico"):
        detalle = marcadas["Alergia antibiótico"].strip()
        agregar("alergia_antibiotico", ALTO, "Alergia a antibióticos",
                f"El formulario 033 la marca ({detalle}): confirmar cuál antes de recetar." if detalle
                else "El formulario 033 la marca sin especificar cuál: confirmarlo antes de recetar.", f)
    if f := en_alergias(AINE):
        agregar("alergia_aine", ALTO, "Alergia a antiinflamatorios (AINE)",
                "No recetar ibuprofeno, aspirina, diclofenaco ni otros AINE.", f)
    if f := en_alergias(ANESTESICOS) or casilla("Alergia anestesia"):
        agregar("alergia_anestesico", ALTO, "Alergia a anestésicos locales",
                "Confirmar el anestésico implicado antes de infiltrar.", f)
    if f := en_alergias(["latex"]):
        agregar("alergia_latex", ALTO, "Alergia al látex", "Guantes y dique sin látex.", f)

    if f := en_medicacion(ANTICOAGULANTES):
        agregar("anticoagulado", ALTO, "Toma anticoagulantes o antiagregantes",
                "Riesgo de sangrado en extracciones y cirugía. Evitar AINE.", f)
    elif f := en_condiciones(HEMORRAGICOS) or casilla("Hemorragias"):
        agregar("hemorragico", ALTO, "Trastorno de la coagulación",
                "Riesgo de sangrado en procedimientos cruentos.", f)
    if f := en_medicacion(BIFOSFONATOS):
        agregar("bifosfonatos", ALTO, "Bifosfonatos o denosumab",
                "Riesgo de osteonecrosis de los maxilares en extracciones e implantes.", f)
    if f := en_condiciones(ENDOCARDITIS):
        agregar("endocarditis", ALTO, "Riesgo de endocarditis",
                "Valorar profilaxis antibiótica antes de procedimientos que sangran.", f)

    if embarazada or embarazada_033:
        agregar("embarazo", ALTO, "Embarazo",
                "Evitar AINE y tetraciclinas; limitar radiografías a lo imprescindible.",
                "Antecedentes: embarazo" if embarazada else "Formulario 033: embarazada")

    if f := (en_condiciones(DIABETES) or de_texto("Medicación", medicacion, DIABETES)
             or casilla("Diabetes")):
        agregar("diabetes", MEDIO, "Diabetes",
                "Cicatrización y riesgo periodontal mayores; confirmar control glucémico.", f)
    if f := (en_condiciones(CARDIOVASCULAR)
             or casilla("Hipertensión arterial") or casilla("Enf. cardíaca")):
        agregar("cardiovascular", MEDIO, "Hipertensión o cardiopatía",
                "Limitar el vasoconstrictor (epinefrina) y tomar la presión antes de intervenir.", f)
    return salida


# ── Receta frente a antecedentes ───────────────────────────────────────
REGLAS_RECETA = [
    ("alergia_penicilina", PENICILINAS, ALTO, "Receta una penicilina ({x}) a un paciente alérgico a penicilinas."),
    ("alergia_penicilina", CEFALOSPORINAS, MEDIO, "Receta una cefalosporina ({x}): posible reacción cruzada con la alergia a penicilinas."),
    ("alergia_antibiotico", PENICILINAS + CEFALOSPORINAS + OTROS_ANTIBIOTICOS, ALTO,
     "Receta un antibiótico ({x}) y el formulario 033 marca alergia a antibióticos sin especificar."),
    ("alergia_aine", AINE, ALTO, "Receta un AINE ({x}) a un paciente alérgico a los AINE."),
    ("anticoagulado", AINE, ALTO, "Receta un AINE ({x}) a un paciente con anticoagulante o antiagregante: aumenta el riesgo de sangrado."),
    ("hemorragico", AINE, MEDIO, "Receta un AINE ({x}) a un paciente con trastorno de la coagulación."),
    ("embarazo", TETRACICLINAS, ALTO, "Receta una tetraciclina ({x}) durante el embarazo: contraindicada."),
    ("embarazo", AINE, MEDIO, "Receta un AINE ({x}) durante el embarazo: evitarlo, sobre todo en el tercer trimestre."),
]


def revisar_receta(texto, alertas):
    """
    Choques entre el texto de una receta y las alertas del paciente.
    Devuelve dicts con nivel, titulo (el choque) y fuente (la alerta).
    """
    presentes = {a["clave"]: a for a in alertas}
    n = normalizar(texto)
    salida, vistos = [], set()
    for clave, raices, nivel, mensaje in REGLAS_RECETA:
        if clave not in presentes:
            continue
        for raiz in raices:
            m = re.search(r"\b" + re.escape(raiz) + r"\w*", n)
            if m and (clave, m.group(0)) not in vistos:
                vistos.add((clave, m.group(0)))
                alerta = presentes[clave]
                salida.append({"clave": clave, "nivel": nivel,
                               "titulo": mensaje.format(x=m.group(0)),
                               "fuente": f"{alerta['titulo']} — {alerta['fuente']}"})
                break
    return salida
