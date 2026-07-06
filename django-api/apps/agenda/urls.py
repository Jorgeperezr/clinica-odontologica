from django.urls import path

from apps.agenda import views

urlpatterns = [
    path("doctors/", views.DoctorListView.as_view(), name="doctor-list"),
    path("appointments/", views.AppointmentListCreateView.as_view(), name="appointment-list"),
    path("appointments/<uuid:pk>/", views.AppointmentDetailView.as_view(), name="appointment-detail"),
    path("appointments/<uuid:pk>/confirm/", views.AppointmentConfirmView.as_view(), name="appointment-confirm"),
    path("appointments/<uuid:pk>/cancel/", views.AppointmentCancelView.as_view(), name="appointment-cancel"),
    path("appointments/<uuid:pk>/reschedule/", views.AppointmentRescheduleView.as_view(), name="appointment-reschedule"),
    path("appointments/<uuid:pk>/checkin/", views.AppointmentCheckinView.as_view(), name="appointment-checkin"),
    path("appointments/<uuid:pk>/checkout/", views.AppointmentCheckoutView.as_view(), name="appointment-checkout"),
    path("agenda/view/", views.AgendaViewList.as_view(), name="agenda-view"),
]
