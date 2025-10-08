from django.urls import path
from . import views

urlpatterns = [
    path('', views.read_root),
    path('session/', views.create_realtime_session),
    path('api/session', views.create_realtime_session),
    path('health', views.health_check),
]
