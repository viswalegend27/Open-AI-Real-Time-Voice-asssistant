from django.urls import path
from . import views

urlpatterns = [
    path('', views.read_root),
    path('session/', views.create_realtime_session),
    path('api/session', views.create_realtime_session),
    path('api/conversation', views.save_conversation),
    path('api/analysis', views.get_analysis),
    path('api/recommendations', views.get_recommendations),
    path('api/generate-summary', views.generate_summary),  # Generate new summary
    path('api/summary/<str:session_id>/', views.get_summary),  # Get existing summary
    path('health', views.health_check),

    # Admin API for vehicle interests
    path('api/vehicle-interests/', views.list_vehicle_interests, name='list_vehicle_interests'),
]
