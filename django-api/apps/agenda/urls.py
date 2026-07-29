from django.urls import path

from apps.agenda import views
from apps.agenda.calendar_feed import doctor_calendar_feed

urlpatterns = [
    path("doctors/", views.DoctorListView.as_view(), name="doctor-list"),
    path("appointments/", views.AppointmentListCreateView.as_view(), name="appointment-list"),
    path("appointments/<uuid:pk>/", views.AppointmentDetailView.as_view(), name="appointment-detail"),
    path("appointments/<uuid:pk>/confirm/", views.AppointmentConfirmView.as_view(), name="appointment-confirm"),
    path("appointments/<uuid:pk>/cancel/", views.AppointmentCancelView.as_view(), name="appointment-cancel"),
    path("appointments/<uuid:pk>/reschedule/", views.AppointmentRescheduleView.as_view(), name="appointment-reschedule"),
    path("appointments/waiting/", views.WaitingPatientsView.as_view(), name="appointments-waiting"),
    path("appointments/<uuid:pk>/checkin/", views.AppointmentCheckinView.as_view(), name="appointment-checkin"),
    path("appointments/<uuid:pk>/start/", views.AppointmentStartView.as_view(), name="appointment-start"),
    path("doctors/me/signature/", views.DoctorMySignatureView.as_view(), name="doctor-my-signature"),
    path("doctors/<uuid:pk>/calendar-url/", views.DoctorCalendarURLView.as_view(), name="doctor-calendar-url"),
    path("calendar/<uuid:token>.ics", doctor_calendar_feed, name="doctor-calendar-feed"),
    path("appointments/<uuid:pk>/checkout/", views.AppointmentCheckoutView.as_view(), name="appointment-checkout"),
    path("agenda/view/", views.AgendaViewList.as_view(), name="agenda-view"),
]
