"""
Un módulo apagado se rechaza en la API, no solo se esconde en el panel.

Esconder el botón es cortesía; el candado es esto. Sin él, cualquiera
que conozca la URL —o que tuviera la pestaña abierta cuando se apagó—
sigue usando un módulo que su clínica no tiene, y el día que eso importe
se descubre por una factura o por un dato que no debería existir.

    permission_classes = [RequiereFuncionalidad.para("inventario")]
"""

from rest_framework.permissions import BasePermission

from apps.common.funcionalidades import CATALOGO, activa


class RequiereFuncionalidad(BasePermission):
    clave = ""

    @classmethod
    def para(cls, clave):
        assert clave in CATALOGO, f"Funcionalidad desconocida: {clave}"
        return type("RequiereFuncionalidadConcreta", (cls,), {"clave": clave})

    @property
    def message(self):
        nombre = CATALOGO.get(self.clave, {}).get("nombre", self.clave)
        return (
            f"«{nombre}» no está activo en esta clínica. "
            "Pídeselo al administrador de la plataforma."
        )

    def has_permission(self, request, view):
        # El Super Administrador opera sobre la plataforma y no dentro de
        # una clínica: no tiene tenant y estas rutas no son suyas.
        return activa(getattr(request, "tenant", None), self.clave)
