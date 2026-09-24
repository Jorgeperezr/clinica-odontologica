"""
Qué módulos tiene contratada cada clínica.

El catálogo vive aquí y no repartido por el código porque es la lista
que el Super Administrador ve al dar de alta una clínica, la que el
panel usa para esconder lo que no toca y la que la API usa para
rechazar lo que no corresponde. Tres sitios, una sola fuente.

**Lo básico no se apaga.** Pacientes, agenda, historia clínica y pagos
no están en esta lista: una clínica odontológica sin ficha de paciente
no es una versión reducida del producto, es un producto que no sirve.
Lo que se puede apagar es lo que una clínica pequeña puede no querer
—o no pagar— sin dejar de trabajar.

**Apagar algo NO borra sus datos.** Si una clínica desactiva inventario
y lo vuelve a activar el mes que viene, su stock sigue ahí. Apagar es
dejar de ver y de poder tocar, no destruir.
"""

CATALOGO = {
    "logros": {
        "nombre": "Rachas y logros",
        "descripcion": "Premiar al paciente que acude a sus controles. Se ve en su app.",
    },
    "inventario": {
        "nombre": "Inventario",
        "descripcion": "Control de stock e insumos por tratamiento.",
    },
    "whatsapp": {
        "nombre": "Recordatorios por WhatsApp",
        "descripcion": "Avisos automáticos de cita. Necesita conectar la cuenta de la clínica.",
    },
    "convenios": {
        "nombre": "Convenios y tarifarios",
        "descripcion": "Precios pactados con aseguradoras y empresas.",
    },
    "app_paciente": {
        "nombre": "App del paciente",
        "descripcion": "Sus citas, su saldo y sus indicaciones en el teléfono.",
    },
    "odontograma_3d": {
        "nombre": "Odontograma 3D",
        "descripcion": "La vista tridimensional. El odontograma clásico no se apaga.",
    },
    "formulario_033": {
        "nombre": "Formulario MSP 033",
        "descripcion": "Historia clínica única del Ministerio de Salud (HCU-033).",
    },
    "reportes": {
        "nombre": "Reportes",
        "descripcion": "Informes financieros y de producción.",
    },
}

# Lo que lleva una clínica recién creada si nadie dice otra cosa.
#
# Todo encendido menos WhatsApp, y no por capricho: WhatsApp no funciona
# hasta que la clínica conecte SU cuenta de Meta, así que dejarlo
# encendido de fábrica pondría en el panel un módulo que no manda nada y
# que parece estropeado.
POR_DEFECTO = {clave: clave != "whatsapp" for clave in CATALOGO}


def normalizar(valor):
    """
    Deja el diccionario con exactamente las claves del catálogo.

    Las que no se conozcan se tiran —serán de una versión anterior— y
    las que falten se rellenan con el valor por defecto. Así, añadir una
    funcionalidad nueva no obliga a migrar los datos de nadie: las
    clínicas que ya existen la reciben encendida en cuanto se despliega.
    """
    entrante = valor if isinstance(valor, dict) else {}
    return {
        clave: bool(entrante.get(clave, POR_DEFECTO[clave]))
        for clave in CATALOGO
    }


def activa(tenant, clave):
    """¿Esta clínica tiene esta funcionalidad?"""
    if tenant is None:
        return False
    return normalizar(getattr(tenant, "funcionalidades", None)).get(clave, False)
