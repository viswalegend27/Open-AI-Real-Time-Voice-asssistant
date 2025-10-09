from django.urls import path
from . import views

urlpatterns = [
    path('', views.read_root),
    path('session/', views.create_realtime_session),
    path('api/session', views.create_realtime_session),
    path('api/conversation', views.save_conversation),
    path('api/analysis', views.get_analysis),
    path('api/recommendations', views.get_recommendations),
    path('health', views.health_check),
]
