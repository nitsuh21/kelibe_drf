#type: ignore
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework_simplejwt.views import TokenObtainPairView
from django.core.mail import send_mail
from django.conf import settings
import secrets
from datetime import datetime
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import os
import random
from django.db.models import Q
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    QuestionCategory,
    Question,
    QuestionChoice,
    UserAnswer,
    UserMatch
)
from .serializers import (
    UserSerializer,
    UserRegistrationSerializer,
    CustomTokenObtainPairSerializer,
    ChangePasswordSerializer,
    QuestionCategorySerializer,
    QuestionSerializer,
    UserAnswerSerializer,
    UserMatchSerializer,
    UserMatchUpdateSerializer,
    EmailVerificationSerializer,
    GoogleAuthSerializer
)

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = UserRegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            # Create user
            user = serializer.save()
            
            # Generate 6-digit OTP
            otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            user.email_verification_token = otp
            user.save()

            # Send verification email with OTP
            send_mail(
                'Verify your email',
                f'Your verification code is: {otp}',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            
            return Response({
                'message': 'Registration successful. Please check your email for verification code.',
                'email': user.email
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        # Add email_verified status to response
        user = User.objects.get(email=request.data['email'])
        response.data['email_verified'] = user.email_verified
        
        if not user.email_verified:
            # Generate new OTP if user is not verified
            otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            user.email_verification_token = otp
            user.save()
            
            # Send new verification email
            send_mail(
                'Verify your email',
                f'Your verification code is: {otp}',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            
            response.data['message'] = 'Please verify your email. A new verification code has been sent.'
        
        return response

class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]



class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

class QuestionCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = QuestionCategory.objects.all()
    serializer_class = QuestionCategorySerializer
    permission_classes = [permissions.IsAuthenticated]

class UserAnswerView(generics.ListCreateAPIView):
    serializer_class = UserAnswerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserAnswer.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
        self._update_matching_score(self.request.user)

    def _update_matching_score(self, user):
        # Update the user's matching score based on their answers
        answers = UserAnswer.objects.filter(user=user)
        if answers.exists():
            # Simple scoring: average of all answers
            score = sum(answer.scale_value or 0 for answer in answers) / answers.count()
            user.matching_score = score
            user.last_score_update = datetime.now()
            user.save()

class MatchingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        # Get all users except the current user and already matched users
        existing_matches = UserMatch.objects.filter(
            Q(user1=user) | Q(user2=user)
        ).values_list('user1_id', 'user2_id')
        
        matched_users = set()
        for match in existing_matches:
            matched_users.add(match[0])
            matched_users.add(match[1])
        
        potential_matches = User.objects.filter(
            email_verified=True  # Only match with verified users
        ).exclude(
            id__in=matched_users
        ).exclude(
            id=user.id
        )

        matches = []
        user_vector = self._get_user_answer_vector(user)
        
        if user_vector is not None:
            for potential_match in potential_matches:
                match_vector = self._get_user_answer_vector(potential_match)
                if match_vector is not None:
                    # Calculate similarity score
                    similarity = cosine_similarity([user_vector], [match_vector])[0][0]
                    if similarity > 0.5:  # Minimum threshold for matching
                        match = UserMatch.objects.create(
                            user1=user,
                            user2=potential_match,
                            compatibility_score=float(similarity)
                        )
                        matches.append(match)

        serializer = UserMatchSerializer(matches, many=True)
        return Response(serializer.data)

    def _get_user_answer_vector(self, user):
        answers = UserAnswer.objects.filter(user=user).select_related('question')
        if not answers.exists():
            return None
            
        vector = []
        for answer in answers:
            if answer.question.question_type in ['single_choice', 'scale']:
                choices = answer.selected_choices.all()
                if choices.exists():
                    vector.append(choices.first().value)
                else:
                    vector.append(0)
            elif answer.question.question_type == 'multiple_choice':
                choices = answer.selected_choices.all()
                vector.extend([choice.value for choice in choices])
            elif answer.question.question_type == 'short_answer':
                # For text answers, we'll use a simple length-based metric
                vector.append(len(answer.text_answer.strip()))
                
        return np.array(vector) if vector else None

class UserMatchUpdateView(generics.UpdateAPIView):
    serializer_class = UserMatchUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        match_id = self.kwargs['pk']
        return get_object_or_404(
            UserMatch,
            id=match_id,
            user2=self.request.user,
            status='pending'
        )

class EmailVerificationView(generics.GenericAPIView):
    serializer_class = EmailVerificationSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        
        try:
            user = User.objects.get(email=email, email_verification_token=otp)
            if user.email_verified:
                return Response(
                    {'detail': 'Email already verified'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user.email_verified = True
            user.email_verification_token = ''
            user.save()
            
            # Return user data and tokens
            refresh = RefreshToken.for_user(user)
            return Response({
                'message': 'Email verified successfully',
                'user': UserSerializer(user).data,
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            })
            
        except User.DoesNotExist:
            return Response(
                {'detail': 'Invalid verification code'},
                status=status.HTTP_400_BAD_REQUEST
            )

class GoogleAuthView(generics.GenericAPIView):
    serializer_class = GoogleAuthSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        idinfo = serializer.validated_data['idinfo']
        email = idinfo['email']
        
        # Check if user exists
        try:
            user = User.objects.get(email=email)
            # If user exists but was created through regular signup
            if not user.is_active:
                return Response(
                    {'detail': 'Please verify your email first'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except User.DoesNotExist:
            # Create new user
            user = User.objects.create_user(
                email=email,
                first_name=idinfo.get('given_name', ''),
                last_name=idinfo.get('family_name', ''),
                is_active=True  # Google users are automatically verified
            )
            
            # Create profile
            Profile.objects.create(
                user=user,
                avatar=idinfo.get('picture', None)
            )
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data
        })


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        request.user.auth_token.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)