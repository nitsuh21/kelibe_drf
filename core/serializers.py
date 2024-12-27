from rest_framework import serializers
from .models import Category, Question, UserResponse

class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'text', 'question_type', 'options', 'min_value', 'max_value', 'required', 'order']

class CategorySerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)
    completion_percentage = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'title', 'description', 'icon', 'color', 'order', 'questions', 'completion_percentage']

    def get_completion_percentage(self, obj):
        user = self.context.get('request').user
        return obj.get_completion_percentage(user)

class UserResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserResponse
        fields = ['id', 'question', 'response', 'created_at', 'updated_at']
        read_only_fields = ['user']

    def validate(self, data):
        # Get the question instance
        question = data['question']
        response = data.get('response')

        # Check if response is required
        if question.required and response is None:
            raise serializers.ValidationError({
                'response': 'This field is required.'
            })

        # Validate response based on question type
        if response is not None:
            if question.question_type == 'single_choice':
                if not isinstance(response, str) or response not in question.options:
                    raise serializers.ValidationError({
                        'response': 'Invalid choice selected.'
                    })

            elif question.question_type == 'multiple_choice':
                if not isinstance(response, list) or not all(opt in question.options for opt in response):
                    raise serializers.ValidationError({
                        'response': 'Invalid choices selected.'
                    })

            elif question.question_type == 'scale':
                if not isinstance(response, int) or not (question.min_value <= response <= question.max_value):
                    raise serializers.ValidationError({
                        'response': f'Response must be a number between {question.min_value} and {question.max_value}.'
                    })

            elif question.question_type == 'boolean':
                if not isinstance(response, bool):
                    raise serializers.ValidationError({
                        'response': 'Response must be a boolean value.'
                    })

        return data

    def create(self, validated_data):
        # Attach the current user to the response
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

class CategoryDetailSerializer(CategorySerializer):
    """Detailed category serializer including user responses"""
    user_responses = serializers.SerializerMethodField()

    class Meta(CategorySerializer.Meta):
        fields = CategorySerializer.Meta.fields + ['user_responses']

    def get_user_responses(self, obj):
        user = self.context['request'].user
        responses = UserResponse.objects.filter(
            user=user,
            question__category=obj
        ).select_related('question')
        
        return {
            str(response.question.id): response.response
            for response in responses
        }
