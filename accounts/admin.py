from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import Profile, QuestionCategory, Question, QuestionChoice, UserAnswer, UserMatch

User = get_user_model()

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_active', 'email_verified')
    list_filter = ('is_staff', 'is_active', 'email_verified')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    inlines = (ProfileInline,)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name')}),
        (_('Email verification'), {'fields': ('email_verified', 'email_verification_token')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser',
                                     'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login',)}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name'),
        }),
    )

@admin.register(QuestionCategory)
class QuestionCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'weight', 'order')
    search_fields = ('name',)
    ordering = ('order', 'name')

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'category', 'question_type', 'required', 'order')
    list_filter = ('category', 'question_type', 'required')
    search_fields = ('text',)
    ordering = ('category', 'order')

@admin.register(QuestionChoice)
class QuestionChoiceAdmin(admin.ModelAdmin):
    list_display = ('question', 'text', 'value', 'order')
    list_filter = ('question',)
    search_fields = ('text',)
    ordering = ('question', 'order')

@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ('user', 'question', 'text_answer', 'created_at')
    list_filter = ('user', 'question')
    search_fields = ('user__email', 'question__text')
    ordering = ('-created_at',)

@admin.register(UserMatch)
class UserMatchAdmin(admin.ModelAdmin):
    list_display = ('user1', 'user2', 'compatibility_score', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('user1__email', 'user2__email')
    ordering = ('-compatibility_score',)
