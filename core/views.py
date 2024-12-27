from django.shortcuts import render

# Create your views here.

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.shortcuts import get_object_or_404

from .models import Category, Question, UserResponse
from .serializers import (
    CategorySerializer,
    CategoryDetailSerializer,
    QuestionSerializer,
    UserResponseSerializer,
)

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.prefetch_related('questions').all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CategoryDetailSerializer
        return CategorySerializer

    @action(detail=True, methods=['get'])
    def questions(self, request, pk=None):
        category = self.get_object()
        questions = category.questions.all()
        serializer = QuestionSerializer(questions, many=True)
        return Response(serializer.data)

class UserResponseViewSet(viewsets.ModelViewSet):
    serializer_class = UserResponseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserResponse.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """
        Update multiple responses at once for a category
        Expected format:
        {
            "category_id": "1",
            "responses": [
                {"question": 1, "response": "answer"},
                {"question": 2, "response": ["option1", "option2"]}
            ]
        }
        """
        category_id = request.data.get('category_id')
        responses_data = request.data.get('responses', [])

        if not category_id or not responses_data:
            return Response(
                {'error': 'Both category_id and responses are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        category = get_object_or_404(Category, id=category_id)
        
        # Validate all questions belong to the category
        question_ids = [resp['question'] for resp in responses_data]
        valid_questions = set(category.questions.values_list('id', flat=True))
        if not all(qid in valid_questions for qid in question_ids):
            return Response(
                {'error': 'All questions must belong to the specified category'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                for response_data in responses_data:
                    question_id = response_data['question']
                    response_value = response_data['response']

                    # Update or create response
                    response, created = UserResponse.objects.update_or_create(
                        user=request.user,
                        question_id=question_id,
                        defaults={'response': response_value}
                    )

            # Return updated category data
            serializer = CategoryDetailSerializer(
                category,
                context={'request': request}
            )
            return Response(serializer.data)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
