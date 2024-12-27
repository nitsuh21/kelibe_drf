#type: ignore

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import (
    Profile,
    QuestionCategory,
    Question,
    QuestionChoice,
    UserAnswer,
    UserMatch
)
from google.oauth2 import id_token
import requests
import random
from django.core.mail import send_mail
from django.conf import settings

User = get_user_model()


class ProfileSerializer(serializers.ModelSerializer):
    age = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = ['phone_number', 'bio', 'location', 'avatar', 'birth_date', 
                 'gender', 'looking_for', 'min_age_preference', 'max_age_preference',
                  'age']
        read_only_fields = ['age']

    def get_age(self, obj):
        if obj.birth_date:
            from datetime import date
            today = date.today()
            return today.year - obj.birth_date.year - ((today.month, today.day) < (obj.birth_date.month, obj.birth_date.day))
        return None


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    profile = ProfileSerializer(required=False)

    class Meta:
        model = User
        fields = ('email', 'password', 'password2', 'first_name', 'last_name', 'profile')
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True}
        }

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password2": "Password fields didn't match."})
        return data

    def create(self, validated_data):
        profile_data = validated_data.pop('profile', {})
        password2 = validated_data.pop('password2', None)
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        
        # Create user with email_verified=False
        validated_data['email_verified'] = False
        user = User.objects.create_user(
            email=email,
            password=password,
            **validated_data
        )

        # Update profile if data provided
        if profile_data:
            profile = user.profile  # Profile is already created by the signal
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

        return user

class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer()

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'email_verified', 'profile')
        read_only_fields = ('id', 'email_verified')

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', {})
        # Update User fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update Profile fields
        if profile_data:
            for attr, value in profile_data.items():
                setattr(instance.profile, attr, value)
            instance.profile.save()

        return instance


class EmailVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField()  

    def validate_otp(self, value):
        if not value:
            raise serializers.ValidationError('Verification code is required')
        return value

    def validate(self, attrs):
        email = attrs.get('email')
        otp = attrs.get('otp')

        if not User.objects.filter(email=email).exists():
            raise serializers.ValidationError({'email': 'No user found with this email'})

        return attrs


class GoogleAuthSerializer(serializers.Serializer):
    token = serializers.CharField()
    
    def validate(self, attrs):
        token = attrs.get('token')
        try:
            # Verify the Google token
            idinfo = id_token.verify_oauth2_token(
                token, requests.Request(), settings.GOOGLE_OAUTH2_CLIENT_ID)
            
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise ValueError('Wrong issuer.')
                
            attrs['idinfo'] = idinfo
            return attrs
        except ValueError:
            raise serializers.ValidationError('Invalid token')


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        return data


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect")
        return value


class QuestionChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionChoice
        fields = ['id', 'text', 'value', 'order']


class QuestionSerializer(serializers.ModelSerializer):
    choices = QuestionChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'category', 'text', 'question_type', 'required', 
                 'order', 'choices', 'created_at', 'updated_at']


class QuestionCategorySerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = QuestionCategory
        fields = ['id', 'name', 'description', 'weight', 'order', 'questions']


class UserAnswerSerializer(serializers.ModelSerializer):
    selected_choices = QuestionChoiceSerializer(many=True, read_only=True)
    selected_choice_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = UserAnswer
        fields = ['id', 'question', 'selected_choices', 'selected_choice_ids',
                 'text_answer', 'created_at', 'updated_at']

    def validate(self, data):
        question = data['question']
        selected_choice_ids = data.get('selected_choice_ids', [])
        text_answer = data.get('text_answer', '')

        if question.question_type in ['single_choice', 'multiple_choice']:
            if not selected_choice_ids:
                if question.required:
                    raise serializers.ValidationError("This question requires at least one choice selection")
            elif question.question_type == 'single_choice' and len(selected_choice_ids) > 1:
                raise serializers.ValidationError("This question only allows one choice")
            
            # Validate that all choices belong to the question
            valid_choice_ids = set(question.choices.values_list('id', flat=True))
            if not all(choice_id in valid_choice_ids for choice_id in selected_choice_ids):
                raise serializers.ValidationError("Invalid choice selection")

        elif question.question_type == 'short_answer':
            if question.required and not text_answer:
                raise serializers.ValidationError("This question requires a text answer")

        return data

    def create(self, validated_data):
        selected_choice_ids = validated_data.pop('selected_choice_ids', [])
        answer = UserAnswer.objects.create(**validated_data)
        if selected_choice_ids:
            answer.selected_choices.set(selected_choice_ids)
        return answer

    def update(self, instance, validated_data):
        selected_choice_ids = validated_data.pop('selected_choice_ids', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if selected_choice_ids is not None:
            instance.selected_choices.set(selected_choice_ids)
        
        instance.save()
        return instance


class UserMatchSerializer(serializers.ModelSerializer):
    matched_user = serializers.SerializerMethodField()

    class Meta:
        model = UserMatch
        fields = ['id', 'matched_user', 'compatibility_score', 
                 'created_at', 'status']
        read_only_fields = ['compatibility_score']

    def get_matched_user(self, obj):
        request = self.context.get('request')
        if request:
            if obj.user1 == request.user:
                matched_user = obj.user2
            else:
                matched_user = obj.user1
            return UserSerializer(matched_user).data
        return None


class UserMatchUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserMatch
        fields = ['status']

    def validate_status(self, value):
        if value not in ['accepted', 'rejected']:
            raise serializers.ValidationError("Status must be either 'accepted' or 'rejected'")
        return value
