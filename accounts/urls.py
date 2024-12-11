from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from allauth.socialaccount.views import signup

from .views import (
    RegisterView,
    CustomTokenObtainPairView,
    ChangePasswordView,
    UpdateProfileView,
    UserProfileView,
    EmailVerificationView,
    GoogleLoginView,
)

app_name = 'accounts'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('profile/update/', UpdateProfileView.as_view(), name='update_profile'),
    path('verify-email/', EmailVerificationView.as_view(), name='verify_email'),
    
    # Social Auth URLs
    path('social/', include('allauth.socialaccount.urls')),
    path('google/login/', GoogleLoginView.as_view(), name='google_login'),
]
