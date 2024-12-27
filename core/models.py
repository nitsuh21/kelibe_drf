from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _

User = get_user_model()

class Category(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50)  # Store icon name/identifier
    color = models.CharField(max_length=7)  # Hex color code
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['order', 'title']

    def __str__(self):
        return self.title

    def get_completion_percentage(self, user):
        """Calculate the completion percentage for a user in this category."""
        questions_count = self.questions.count()
        if questions_count == 0:
            return 0
        
        answered_count = UserResponse.objects.filter(
            question__category=self,
            user=user,
            response__isnull=False
        ).count()
        
        return int((answered_count / questions_count) * 100)

class QuestionType(models.TextChoices):
    SHORT_ANSWER = 'short_answer', _('Short Answer')
    SINGLE_CHOICE = 'single_choice', _('Single Choice')
    MULTIPLE_CHOICE = 'multiple_choice', _('Multiple Choice')
    SCALE = 'scale', _('Scale')
    BOOLEAN = 'boolean', _('Yes/No')

class Question(models.Model):
    category = models.ForeignKey(Category, related_name='questions', on_delete=models.CASCADE)
    text = models.TextField()
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.SHORT_ANSWER
    )
    options = models.JSONField(
        null=True, 
        blank=True,
        help_text="Options for choice-based questions. Format: ['option1', 'option2', ...]"
    )
    min_value = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Minimum value for scale questions"
    )
    max_value = models.IntegerField(
        null=True,
        blank=True,
        validators=[MaxValueValidator(10)],
        help_text="Maximum value for scale questions"
    )
    required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'order', 'created_at']

    def __str__(self):
        return f"{self.category.title} - {self.text[:50]}"

    def clean(self):
        from django.core.exceptions import ValidationError
        
        if self.question_type in [QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE]:
            if not self.options:
                raise ValidationError(
                    {'options': _('Options are required for choice-based questions.')}
                )
        
        if self.question_type == QuestionType.SCALE:
            if self.min_value is None or self.max_value is None:
                raise ValidationError(
                    {'min_value': _('Min and max values are required for scale questions.')}
                )
            if self.min_value >= self.max_value:
                raise ValidationError(
                    {'min_value': _('Min value must be less than max value.')}
                )

class UserResponse(models.Model):
    user = models.ForeignKey(User, related_name='responses', on_delete=models.CASCADE)
    question = models.ForeignKey(Question, related_name='responses', on_delete=models.CASCADE)
    response = models.JSONField(
        null=True,
        blank=True,
        help_text="Stores the user's response. Format depends on question type."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'question']
        ordering = ['question__category', 'question__order']

    def __str__(self):
        return f"{self.user.username} - {self.question.text[:50]}"

    def clean(self):
        from django.core.exceptions import ValidationError
        
        if self.response is not None:
            if self.question.question_type == QuestionType.SINGLE_CHOICE:
                if not isinstance(self.response, str) or self.response not in self.question.options:
                    raise ValidationError(
                        {'response': _('Invalid choice selected.')}
                    )
            
            elif self.question.question_type == QuestionType.MULTIPLE_CHOICE:
                if not isinstance(self.response, list) or not all(opt in self.question.options for opt in self.response):
                    raise ValidationError(
                        {'response': _('Invalid choices selected.')}
                    )
            
            elif self.question.question_type == QuestionType.SCALE:
                if not isinstance(self.response, int) or not (self.question.min_value <= self.response <= self.question.max_value):
                    raise ValidationError(
                        {'response': _('Response must be a number within the defined range.')}
                    )
            
            elif self.question.question_type == QuestionType.BOOLEAN:
                if not isinstance(self.response, bool):
                    raise ValidationError(
                        {'response': _('Response must be a boolean value.')}
                    )
