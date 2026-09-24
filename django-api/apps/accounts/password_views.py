"""
Que cada uno elija su propia contraseña (Sprint 92).

No había forma de hacerlo. Existía el restablecimiento por correo para el
personal y la contraseña temporal que entrega el Super Administrador,
pero ninguna manera de que alguien ya dentro cambiara la suya. Con eso,
la contraseña que el dueño de la plataforma entrega al dar de alta una
clínica se queda vigente para siempre — y él la conoce.
"""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView


class CambiarMiContrasenaView(APIView):
    """
    POST /api/v1/auth/change-password/ {current_password?, new_password}

    `current_password` se exige SALVO que la contraseña sea temporal: en
    ese caso quien la puso fue otra persona y pedírsela al usuario sería
    pedirle que repita un secreto que no es suyo.
    """

    def post(self, request):
        usuario = request.user
        nueva = str(request.data.get("new_password", ""))
        temporal = bool(getattr(usuario, "must_change_password", False))

        if not temporal:
            actual = str(request.data.get("current_password", ""))
            if not usuario.check_password(actual):
                return Response({"detail": "La contraseña actual no es correcta."},
                                status=400)

        try:
            validate_password(nueva, usuario)
        except ValidationError as e:
            return Response({"detail": " ".join(e.messages)}, status=400)

        if usuario.check_password(nueva):
            return Response(
                {"detail": "La nueva contraseña no puede ser la misma que la anterior."},
                status=400,
            )

        usuario.set_password(nueva)
        usuario.must_change_password = False
        usuario.save(update_fields=["password", "must_change_password"])
        return Response({"detail": "Contraseña actualizada."})
