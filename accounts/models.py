# type: ignore

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(**extra_fields)  # Create user without email first
        user.email = email  # Set email separately
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    email = models.EmailField(_('email address'), unique=True)
    username = None
    email_verified = models.BooleanField(null=False, default=False)
    email_verification_token = models.CharField(max_length=100, blank=True)
    matching_score = models.FloatField(null=False, default=0.0)
    last_score_update = models.DateTimeField(null=True, blank=True)
    first_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    
    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=15, blank=True)
    bio = models.TextField(blank=True)
    location = models.CharField(max_length=100, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    matching_score = models.FloatField(null=True, default=0.0)
    gender = models.CharField(max_length=20, choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ], blank=True)
    
    # Matching preferences
    looking_for = models.CharField(max_length=20, choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('both', 'Both'),
    ], blank=True)
    min_age_preference = models.IntegerField(null=True, blank=True)
    max_age_preference = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"Profile of {self.user.email}"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

class QuestionCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    weight = models.FloatField(default=1.0)  # For AI matching weight
    order = models.IntegerField(default=0)  # For ordering categories

    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = 'Question Categories'

    def __str__(self):
        return self.name

class Question(models.Model):
    QUESTION_TYPES = [
        ('single_choice', 'Single Choice'),
        ('multiple_choice', 'Multiple Choice'),
        ('short_answer', 'Short Answer'),
        ('scale', 'Scale'),
    ]

    category = models.ForeignKey(QuestionCategory, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    required = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'order', 'created_at']

    def __str__(self):
        return self.text

class QuestionChoice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=255)
    value = models.IntegerField()
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['question', 'order']
        unique_together = ['question', 'value']

    def __str__(self):
        return f"{self.question.text[:30]} - {self.text}"

class UserAnswer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_choices = models.ManyToManyField(QuestionChoice, blank=True, related_name='user_answers')
    text_answer = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'question']

    def __str__(self):
        return f"{self.user.email} - {self.question.text[:30]}"

class UserMatch(models.Model):
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='matches_as_user1')
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='matches_as_user2')
    compatibility_score = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ], default='pending')

    class Meta:
        unique_together = ['user1', 'user2']

    def __str__(self):
        return f"{self.user1.email} - {self.user2.email} ({self.compatibility_score})"
