from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.pagination import PageNumberPagination
from accounts.authentication import CustomJWEAuthentication
from files.models import FileObject
from files.serializers import FileObjectSerializer
from django.db import models

class TrashedListAPIView(APIView):
    authentication_classes = [CustomJWEAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        
        trashed_items = FileObject.objects.filter(
            owner=user, 
            trashed_at__isnull=False  # is trashed
        ).filter(
            # Either has no parent, or parent is not trashed
            models.Q(parent__isnull=True) | models.Q(parent__trashed_at__isnull=True)
        ).order_by('-trashed_at')

        # Paginate
        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(trashed_items, request)
        serializer = FileObjectSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
