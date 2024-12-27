from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, UserResponseViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'responses', UserResponseViewSet, basename='response')

urlpatterns = [
    path('', include(router.urls)),
]
