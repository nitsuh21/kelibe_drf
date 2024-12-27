from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Question, UserResponse

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'colored_box', 'description', 'order', 'question_count', 'created_at')
    list_editable = ('order',)
    search_fields = ('title', 'description')
    ordering = ('order', 'title')
    readonly_fields = ('created_at', 'updated_at')

    def colored_box(self, obj):
        return format_html(
            '<div style="background-color: {}; width: 20px; height: 20px; border-radius: 4px;"></div>',
            obj.color
        )
    colored_box.short_description = 'Color'

    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = 'Questions'

class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ('text', 'question_type', 'required', 'order')
    ordering = ('order',)
    show_change_link = True

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'category', 'question_type', 'required', 'order', 'response_count')
    list_filter = ('category', 'question_type', 'required')
    search_fields = ('text', 'category__title')
    ordering = ('category', 'order')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('order', 'required')

    fieldsets = (
        (None, {
            'fields': ('category', 'text', 'question_type', 'required', 'order')
        }),
        ('Choice Options', {
            'fields': ('options',),
            'classes': ('collapse',),
            'description': 'For choice-based questions, enter options as a list'
        }),
        ('Scale Settings', {
            'fields': ('min_value', 'max_value'),
            'classes': ('collapse',),
            'description': 'For scale questions, specify the range'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def response_count(self, obj):
        return obj.responses.count()
    response_count.short_description = 'Responses'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj and obj.question_type not in ['single_choice', 'multiple_choice']:
            form.base_fields['options'].widget.attrs['disabled'] = True
        if obj and obj.question_type != 'scale':
            form.base_fields['min_value'].widget.attrs['disabled'] = True
            form.base_fields['max_value'].widget.attrs['disabled'] = True
        return form

@admin.register(UserResponse)
class UserResponseAdmin(admin.ModelAdmin):
    list_display = ('user', 'question', 'get_category', 'response_preview', 'created_at')
    list_filter = ('question__category', 'user', 'created_at')
    search_fields = ('user__username', 'question__text', 'question__category__title')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('user', 'question')

    def get_category(self, obj):
        return obj.question.category
    get_category.short_description = 'Category'
    get_category.admin_order_field = 'question__category'

    def response_preview(self, obj):
        if obj.response is None:
            return '-'
        if isinstance(obj.response, list):
            return ', '.join(str(x) for x in obj.response[:3]) + ('...' if len(obj.response) > 3 else '')
        return str(obj.response)[:50]
    response_preview.short_description = 'Response'
