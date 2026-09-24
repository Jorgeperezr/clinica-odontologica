"""
Funciones de cada profesional: qué módulos puede usar dentro de su clínica.

El rol sigue mandando en lo clínico (quién escribe en la historia, quién
firma una receta), y eso no se toca aquí. Lo que se decide por persona son
los MÓDULOS de gestión, porque ahí cada clínica se organiza distinto: en
una consulta pequeña la doctora agenda sus citas y cobra; en una grande
eso lo hace recepción y el doctor ni lo ve.

Dos juegos de valores por defecto, y la diferencia importa:

  · HEREDADAS: lo que cada rol podía hacer antes de que existieran las
    funciones. Se aplican a quien se creó entonces y no tiene nada
    guardado, para que actualizar no le quite ni le dé nada a nadie.
  · AL_CREAR: lo que se propone marcado al dar de alta a alguien nuevo.
    Es una sugerencia que el administrador cambia en el mismo formulario.

El administrador de la clínica tiene todas, siempre.

Cada función comprueba también la funcionalidad de la clínica de la que
depende: dar «Inventario» a alguien de una clínica que no lo tiene
contratado no abre nada.
"""

from rest_framework.permissions import BasePermission

CATALOGO = {
    "agenda": {
        "etiqueta": "Gestionar la agenda",
        "descripcion": "Crear, mover, confirmar y cancelar citas, y agendar las solicitudes que llegan desde la app.",
        "funcionalidad": None,
    },
    "cobros": {
        "etiqueta": "Cobros y presupuestos",
        "descripcion": "Presupuestos, planes de pago, cobro de cuotas y convenio del paciente.",
        "funcionalidad": None,
    },
    "mensajes_app": {
        "etiqueta": "Responder mensajes de la app",
        "descripcion": "Contestar las preguntas que los pacientes envían desde la aplicación.",
        "funcionalidad": "app_paciente",
    },
    "logros": {
        "etiqueta": "Rachas y logros",
        "descripcion": "Conceder logros y descuentos a los pacientes.",
        "funcionalidad": "logros",
    },
    "inventario": {
        "etiqueta": "Inventario",
        "descripcion": "Productos, lotes, entradas y salidas de material.",
        "funcionalidad": "inventario",
    },
    "reportes": {
        "etiqueta": "Reportes de gestión",
        "descripcion": "Ingresos, pacientes nuevos y resumen de citas de toda la clínica.",
        "funcionalidad": "reportes",
    },
    "whatsapp": {
        "etiqueta": "Configurar WhatsApp",
        "descripcion": "Conectar la cuenta de WhatsApp de la clínica y encender los recordatorios.",
        "funcionalidad": "whatsapp",
    },
}

ROLES_CON_FUNCIONES = ("reception", "doctor", "auxiliary")

# Lo que cada rol podía hacer antes. NO cambiar sin una migración: es lo
# que tiene hoy cada persona creada antes de que existieran las funciones.
HEREDADAS = {
    "reception": {"agenda", "cobros", "mensajes_app"},
    "doctor": {"mensajes_app"},
    "auxiliary": {"inventario"},
}

# Lo que se propone al dar de alta. En la doctora se marca la agenda
# (en la mayoría de consultas agenda sus propias citas) y los logros (el
# programa existe para que el profesional premie la constancia).
AL_CREAR = {
    "reception": {"agenda", "cobros", "mensajes_app"},
    "doctor": {"agenda", "mensajes_app", "logros"},
    "auxiliary": {"inventario"},
}


def _es_admin(usuario):
    return getattr(usuario, "role", None) == "admin" or getattr(usuario, "is_superuser", False)


def al_crear(rol):
    """Funciones marcadas por defecto en el alta de un profesional con este rol."""
    return {clave: clave in AL_CREAR.get(rol, set()) for clave in CATALOGO}


def funciones_de(usuario):
    """Qué funciones tiene de verdad esta persona, clave por clave."""
    if _es_admin(usuario):
        return {clave: True for clave in CATALOGO}
    rol = getattr(usuario, "role", None)
    if rol not in ROLES_CON_FUNCIONES:
        return {clave: False for clave in CATALOGO}
    guardadas = getattr(usuario, "funciones", None) or {}
    heredadas = HEREDADAS.get(rol, set())
    # Una clave que falta toma el valor heredado del rol: así, añadir al
    # catálogo una función nueva no le cambia el acceso a nadie.
    return {clave: bool(guardadas.get(clave, clave in heredadas)) for clave in CATALOGO}


def tiene(usuario, clave):
    return funciones_de(usuario).get(clave, False)


class TieneFuncion(BasePermission):
    """
    Permiso por función. Se usa en lugar de la comprobación de rol de los
    módulos de gestión; el resto de la API sigue con sus roles.

        permission_classes = [TieneFuncion.para("cobros")]
    """

    clave = None
    message = "No tienes asignada esta función en la clínica."

    @classmethod
    def para(cls, clave):
        assert clave in CATALOGO, f"Función desconocida: {clave}"
        return type(f"TieneFuncion_{clave}", (cls,), {"clave": clave})

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if not tiene(u, self.clave):
            return False
        funcionalidad = CATALOGO[self.clave]["funcionalidad"]
        if funcionalidad:
            from apps.common.funcionalidades import activa

            return activa(getattr(request, "tenant", None) or u.tenant, funcionalidad)
        return True
