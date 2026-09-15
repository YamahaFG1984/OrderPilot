from django.urls import path

from . import views

app_name = "workbench"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("po/", views.po_list, name="po_list"),
    path("po/new/", views.po_create, name="po_create"),
    path("po/<int:pk>/", views.po_detail, name="po_detail"),
    path("po/<int:pk>/edit/", views.po_edit, name="po_edit"),
    path("po/<int:pk>/t/<str:name>/", views.po_transition, name="po_transition"),
    path("po/<int:pk>/date/", views.po_change_date, name="po_change_date"),
    path("po/<int:pk>/milestone/<int:mid>/", views.po_milestone, name="po_milestone"),
    path("po/<int:pk>/upload/", views.po_upload, name="po_upload"),
    path("alerts/", views.alert_list, name="alerts"),
    path("alerts/<int:pk>/ack/", views.alert_ack, name="alert_ack"),
    path("alerts/scan/", views.alert_scan, name="alert_scan"),
    path("sync/", views.sync_page, name="sync"),
    path("sync/start/", views.sync_start, name="sync_start"),
    path("sync/jobs/", views.sync_jobs, name="sync_jobs"),
]
