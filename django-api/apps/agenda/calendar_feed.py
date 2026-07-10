"""
Feed iCalendar (ICS) por doctor — Sprint 20, Google Calendar Fase 1.

Cada doctor tiene una URL secreta (calendar_token) que Google Calendar,
Apple Calendar u Outlook pueden SUSCRIBIR ("Agregar por URL"). El
calendario personal del dentista se actualiza solo con las citas de la
clínica: nuevas, reagendadas y canceladas (estas últimas se marcan
CANCELLED, el estándar iCalendar para que el evento desaparezca).

La Fase 2 (bidireccional real: eventos creados en Google bloquean la
agenda de la clínica) requiere credenciales OAuth de Google Cloud — ver
DEPLOY.md. El campo Appointment.google_calendar_event_id ya existe para
ese momento.
"""

from django.http import Http404, HttpResponse

from apps.agenda.models import Appointment, Doctor

STATUS_MAP = {
    Appointment.Status.CANCELLED: "CANCELLED",
    Appointment.Status.CONFIRMED: "CONFIRMED",
}


def _escape(text):
    return str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fmt(dt):
    return dt.strftime("%Y%m%dT%H%M%SZ")


def doctor_calendar_feed(request, token):
    """GET /api/v1/calendar/<token>.ics — sin login: el token ES el secreto."""
    try:
        doctor = Doctor.objects.select_related("user", "tenant").get(calendar_token=token)
    except (Doctor.DoesNotExist, ValueError):
        raise Http404

    appointments = (
        Appointment.objects.filter(doctor=doctor)
        .select_related("patient")
        .order_by("scheduled_start")[:500]  # las 500 más relevantes
    )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Clinica Odontologica//Agenda//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:Citas — {_escape(doctor.full_name)}",
        "X-WR-TIMEZONE:America/Guayaquil",
    ]
    for a in appointments:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{a.id}@clinica-odontologica",
            f"DTSTAMP:{_fmt(a.updated_at if hasattr(a, 'updated_at') else a.scheduled_start)}",
            f"DTSTART:{_fmt(a.scheduled_start)}",
            f"DTEND:{_fmt(a.scheduled_end)}",
            f"SUMMARY:{_escape('Cita: ' + a.patient.full_name)}",
            f"STATUS:{STATUS_MAP.get(a.status, 'TENTATIVE')}",
            f"DESCRIPTION:{_escape('Estado: ' + a.get_status_display() + (' | ' + a.notes if a.notes else ''))}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")

    return HttpResponse(
        "\r\n".join(lines) + "\r\n",
        content_type="text/calendar; charset=utf-8",
    )
