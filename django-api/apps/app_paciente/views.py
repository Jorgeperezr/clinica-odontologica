"""
API de la aplicación móvil del paciente (Sprint 89).

Antes de esto, la app no tenía nada que consumir: el rol `patient`
existía, el login por OTP funcionaba y había marcas `visible_to_patient`
en la historia, pero **ningún endpoint de la API admitía ese rol**. Un
paciente autenticado no podía pedir ni una cita.

Lo que se expone es deliberadamente poco:

  · sus citas,
  · lo que debe y cuándo vence,
  · sus recetas e indicaciones de cuidado, y solo las que el profesional
    marcó como visibles.

Lo que NO se expone, también deliberadamente: notas clínicas internas,
diagnósticos sin revisar, el odontograma, los costes internos de los
tratamientos y cualquier dato de otro paciente. La app es una ventana
para que el paciente se organice, no una copia de su historia.
"""

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.app_paciente.permissions import EsPaciente, ficha_del_paciente


class BaseVistaPaciente(APIView):
    permission_classes = [EsPaciente]


class MiPerfilView(BaseVistaPaciente):
    """GET /api/v1/app/me/ — lo que la app muestra al abrirse."""

    def get(self, request):
        from apps.agenda.models import Appointment
        from apps.billing.models import Installment

        ficha = ficha_del_paciente(request)
        hoy = timezone.localdate()
        ahora = timezone.now()

        pendientes = Installment.objects.filter(
            patient=ficha, tenant=request.tenant,
        ).exclude(status=Installment.Status.PAID)

        proxima = Appointment.objects.filter(
            patient=ficha, tenant=request.tenant,
            scheduled_start__gte=ahora,
        ).exclude(
            status__in=[Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW],
        ).order_by("scheduled_start").select_related("doctor__user").first()

        return Response({
            "nombre": f"{ficha.first_name} {ficha.last_name}".strip(),
            "cedula": ficha.national_id,
            "clinica": request.tenant.name,
            "convenio": ficha.agreement.name if ficha.agreement else None,
            "proxima_cita": _cita(proxima) if proxima else None,
            "cuotas_pendientes": pendientes.count(),
            # `localdate` y no `now().date()`: lo que importa es la fecha
            # de la clínica, no la del servidor (Sprint 74).
            "cuotas_vencidas": pendientes.filter(due_date__lt=hoy).count(),
            "saldo": str(sum((c.amount - c.total_paid for c in pendientes), start=0)),
        })


class MisCitasView(BaseVistaPaciente):
    """GET /api/v1/app/citas/ — las suyas, próximas primero."""

    def get(self, request):
        from apps.agenda.models import Appointment

        ficha = ficha_del_paciente(request)
        citas = Appointment.objects.filter(
            patient=ficha, tenant=request.tenant,
        ).select_related("doctor__user", "treatment").order_by("-scheduled_start")[:60]
        ahora = timezone.now()
        return Response({
            "proximas": [_cita(c) for c in reversed(
                [c for c in citas if c.scheduled_start >= ahora
                 and c.status not in (Appointment.Status.CANCELLED,
                                      Appointment.Status.NO_SHOW)])],
            "anteriores": [_cita(c) for c in citas if c.scheduled_start < ahora],
        })


class MiSaldoView(BaseVistaPaciente):
    """GET /api/v1/app/saldo/ — cuánto debe y cuándo vence cada cuota."""

    def get(self, request):
        from apps.billing.models import Installment

        ficha = ficha_del_paciente(request)
        hoy = timezone.localdate()
        cuotas = Installment.objects.filter(
            patient=ficha, tenant=request.tenant,
        ).prefetch_related("payments").order_by("due_date")

        filas = []
        for c in cuotas:
            pagado = c.total_paid
            filas.append({
                "numero": c.number,
                "vence": c.due_date.isoformat(),
                "monto": str(c.amount),
                "pagado": str(pagado),
                "saldo": str(c.amount - pagado),
                "estado": c.get_status_display(),
                "vencida": c.status != c.Status.PAID and c.due_date < hoy,
            })
        pendiente = sum((c.amount - c.total_paid for c in cuotas
                         if c.status != c.Status.PAID), start=0)
        return Response({"saldo_total": str(pendiente), "cuotas": filas})


class MisIndicacionesView(BaseVistaPaciente):
    """
    GET /api/v1/app/indicaciones/ — recetas e indicaciones de cuidado.

    Solo las marcadas como visibles (RF-APP-03) y solo de esos dos tipos:
    las notas clínicas internas no salen de la clínica. El filtro es por
    lista blanca de tipos y no por exclusión, para que un tipo nuevo no
    acabe publicado en la app por olvido.
    """

    def get(self, request):
        from apps.clinical.models import Evolution

        ficha = ficha_del_paciente(request)
        visibles = Evolution.objects.filter(
            patient=ficha, tenant=request.tenant,
            visible_to_patient=True,
            type__in=[Evolution.Type.PRESCRIPTION, Evolution.Type.CARE_INSTRUCTION],
        ).select_related("doctor__user").order_by("-date")[:80]

        return Response([{
            "id": str(e.id),
            "tipo": e.get_type_display(),
            "fecha": e.date.isoformat(),
            "texto": e.notes,
            "profesional": (e.doctor.user.full_name if e.doctor and e.doctor.user else None),
        } for e in visibles])


class MisLogrosView(BaseVistaPaciente):
    """
    GET /api/v1/app/logros/ — sus rachas y logros.

    Lo que se devuelve es lo CONCEDIDO, no lo que el paciente cumpliría
    hoy si se evaluaran las reglas. Un logro es un hecho con su fecha;
    recalcularlo al leerlo haría que alguien perdiera una medalla por
    faltar a una cita este mes, que es lo contrario de lo que premia un
    programa de fidelidad.

    `racha` cuenta los meses seguidos del mismo logro automático, que es
    lo que la app enseña como «3 meses seguidos».
    """

    def get(self, request):
        from apps.logros.models import LogroDePaciente

        ficha = ficha_del_paciente(request)
        concesiones = LogroDePaciente.objects.filter(
            patient=ficha, tenant=request.tenant,
        ).select_related("logro").order_by("-otorgado_en")[:60]

        por_logro = {}
        for c in concesiones:
            por_logro.setdefault(c.logro_id, []).append(c)

        salida = []
        for c in concesiones:
            hermanos = por_logro[c.logro_id]
            if hermanos[0].id != c.id:
                continue   # solo la más reciente de cada logro
            periodos = sorted(
                (h.periodo for h in hermanos if h.periodo), reverse=True,
            )
            salida.append({
                "id": str(c.id),
                "nombre": c.logro.nombre,
                "descripcion": c.logro.descripcion,
                "icono": c.logro.icono,
                "beneficio": c.logro.beneficio,
                "obtenido": c.otorgado_en.date().isoformat(),
                "veces": len(hermanos),
                "racha": _racha_seguida(periodos),
                "automatico": c.logro.es_automatico,
            })
        return Response(salida)


class MiClinicaView(BaseVistaPaciente):
    """
    GET /api/v1/app/clinica/ — nombre, logotipo y colores de SU clínica.

    Hacía falta un endpoint nuevo en vez de abrir `/config/branding/` al
    rol de paciente: aquel devuelve el registro entero y está pensado
    para el panel. Aquí sale solo lo que la app pinta, y el tenant lo
    decide el token, como todo lo demás de esta app.

    **Los colores llegan ya resueltos**, en #rrggbb. La app no guarda
    ninguna tabla de temas: si la guardara, el día que alguien añada un
    tema al panel la misma clínica se vería de un color en el escritorio
    y de otro en el teléfono.

    El logotipo se devuelve como URL ABSOLUTA porque la app no vive en
    el mismo origen que la API —el panel sí, y por eso a él le vale la
    ruta relativa—. Nginx publica `/media/branding/` y niega el resto de
    `/media/`, así que el logotipo es alcanzable sin token y las
    radiografías no.
    """

    def get(self, request):
        from apps.configuration.models import ClinicBranding
        from apps.configuration.temas import resolver

        # `ficha_del_paciente` no se usa aquí —no hacen falta sus datos—,
        # pero sí su comprobación: una cuenta sin ficha no debe poder
        # recorrer la app, ni siquiera su parte decorativa.
        ficha_del_paciente(request)

        marca = ClinicBranding.objects.filter(tenant=request.tenant).first()
        principal, secundario = resolver(marca.theme if marca else None)

        nombre = ""
        if marca:
            nombre = (marca.display_name or "").strip()
        nombre = nombre or request.tenant.name

        return Response({
            "nombre": nombre,
            "nombre_corto": (marca.short_name or "").strip() if marca else "",
            "logo": _url_absoluta(request, marca.logo.url if marca and marca.logo else None),
            "color_principal": principal,
            "color_secundario": secundario,
            # Para que «llama a tu clínica» deje de ser un consejo vacío.
            "telefono": (marca.phone or "").strip() if marca else "",
            "direccion": (marca.address or "").strip() if marca else "",
            "email": (marca.email or "").strip() if marca else "",
        })


def _url_absoluta(request, ruta):
    if not ruta:
        return None
    return request.build_absolute_uri(ruta)


def _racha_seguida(periodos):
    """
    Meses consecutivos, contando desde el más reciente hacia atrás.

    Se calcula con lo YA concedido y no volviendo a mirar las citas: la
    racha es el historial de premios, no una reevaluación.
    """
    if not periodos:
        return 0
    seguidos = 1
    for anterior, siguiente in zip(periodos, periodos[1:]):
        esperado_mes = anterior.month - 1 or 12
        esperado_anio = anterior.year - (1 if anterior.month == 1 else 0)
        if siguiente.month == esperado_mes and siguiente.year == esperado_anio:
            seguidos += 1
        else:
            break
    return seguidos


def _cita(c):
    """Una cita como la ve el paciente: sin notas internas."""
    return {
        "id": str(c.id),
        "inicio": c.scheduled_start.isoformat(),
        "fin": c.scheduled_end.isoformat(),
        "estado": c.get_status_display(),
        "doctor": (c.doctor.user.full_name if c.doctor and c.doctor.user else None),
        "motivo": c.treatment.name if getattr(c, "treatment", None) else None,
    }
