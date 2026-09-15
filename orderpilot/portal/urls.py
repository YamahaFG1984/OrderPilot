from django.urls import path

from . import views

app_name = "portal"

urlpatterns = [
    path("", views.home, name="home"),
    path("po/<int:pk>/", views.po_detail, name="po_detail"),
    path("po/<int:pk>/t/<str:name>/", views.po_transition, name="po_transition"),
    path("po/<int:pk>/date/", views.po_change_date, name="po_change_date"),
    path("po/<int:pk>/milestone/<int:mid>/", views.po_milestone, name="po_milestone"),
    path("po/<int:pk>/upload/", views.po_upload, name="po_upload"),
]
