from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView,
    CustomTokenObtainPairView,
    UserProfileView,
    QuestionCategoryViewSet,
    UserAnswerView,
    MatchingView,
    UserMatchUpdateView,
    EmailVerificationView,
    GoogleAuthView,
    UserListView,
    LogoutView
)

router = DefaultRouter()
router.register(r'question-categories', QuestionCategoryViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('register/', RegisterView.as_view(), name='register'),
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('verify-email/', EmailVerificationView.as_view(), name='verify-email'),
    path('google/', GoogleAuthView.as_view(), name='google-auth'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('answers/', UserAnswerView.as_view(), name='user-answers'),
    path('matches/', MatchingView.as_view(), name='matches'),
    path('matches/<int:pk>/update/', UserMatchUpdateView.as_view(), name='update-match'),
    path('users/', UserListView.as_view(), name='users'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('logout/', LogoutView.as_view(), name='logout'),
]
