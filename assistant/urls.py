from django.urls import path
from . import views

urlpatterns = [
    path('', views.read_root),
    path('api/session', views.create_realtime_session),
    path('api/conversation', views.save_conversation),
    path('api/generate-summary', views.generate_summary),
    path('api/summary/<str:session_id>/', views.get_summary),
    path('api/vehicle-interests/', views.list_vehicle_interests, name='list_vehicle_interests'),
]