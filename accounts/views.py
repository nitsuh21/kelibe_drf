from django.shortcuts import render
from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from django.core.mail import send_mail
from django.conf import settings
import secrets
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    UserSerializer,
    UserRegistrationSerializer,
    CustomTokenObtainPairSerializer,
    ChangePasswordSerializer,
    UpdateUserSerializer,
    EmailVerificationSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = UserRegistrationSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        # Generate verification token
        token = secrets.token_urlsafe(32)
        user.email_verification_token = token
        user.save()

        # Send verification email
        verification_url = f"http://localhost:3000/verify-email?token={token}"
        send_mail(
            'Verify your email',
            f'Please click the following link to verify your email: {verification_url}',
            settings.EMAIL_HOST_USER,
            [user.email],
            fail_silently=False,
        )


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class ChangePasswordView(generics.UpdateAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = self.get_object()
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        return Response({'detail': 'Password changed successfully.'})


class UpdateProfileView(generics.UpdateAPIView):
    serializer_class = UpdateUserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user


class UserProfileView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user


class EmailVerificationView(APIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = EmailVerificationSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['token']

        try:
            user = User.objects.get(email_verification_token=token)
            if not user.email_verified:
                user.email_verified = True
                user.email_verification_token = ''
                user.save()
                return Response({'detail': 'Email verified successfully.'})
            return Response({'detail': 'Email already verified.'})
        except User.DoesNotExist:
            return Response(
                {'detail': 'Invalid verification token.'},
                status=status.HTTP_400_BAD_REQUEST
            )


class GoogleLoginView(APIView):
    def post(self, request):
        try:
            code = request.data.get('code')
            adapter = GoogleOAuth2Adapter()
            client = OAuth2Client(
                request=request,
                client_id=settings.SOCIALACCOUNT_PROVIDERS['google']['APP']['client_id'],
                client_secret=settings.SOCIALACCOUNT_PROVIDERS['google']['APP']['secret']
            )
            
            token = adapter.get_access_token_for_code(
                request=request,
                code=code,
                client=client
            )
            
            user_data = adapter.get_user_info(token)
            email = user_data.get('email')
            
            # Get or create user
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                user = User.objects.create_user(
                    email=email,
                    first_name=user_data.get('given_name', ''),
                    last_name=user_data.get('family_name', ''),
                    is_active=True,
                    is_verified=True
                )
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                }
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
