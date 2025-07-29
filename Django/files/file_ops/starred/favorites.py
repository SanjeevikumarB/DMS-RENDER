from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from accounts.authentication import CustomJWEAuthentication

from files.models import FileObject, StarredFile
from django.shortcuts import get_object_or_404


class FavoritesListAPIView(APIView):
    authentication_classes = [CustomJWEAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        starred_files = StarredFile.objects.filter(user=request.user).select_related('file')
        response_data = []

        for entry in starred_files:
            file_obj = entry.file
            if file_obj.type == 'folder':
                response_data.append(self.build_file_tree(file_obj))
            else:
                response_data.append({
                    "uid": str(file_obj.uid),
                    "name": file_obj.name,
                    "type": file_obj.type,
                    # "uploaded_url": file_obj.uploaded_url,
                    # "size": file_obj.size,
                    # "modified_at": file_obj.modified_at,
                    "starred_at": entry.starred_at,
                })

        if not response_data:
            return Response({"message": "No favorites."}, status=status.HTTP_200_OK)

        return Response(response_data, status=status.HTTP_200_OK)

    def build_file_tree(self, file_obj):
        node = {
            "uid": str(file_obj.uid),
            "name": file_obj.name,
            "type": file_obj.type,
            # "uploaded_url": file_obj.uploaded_url,
            # "size": file_obj.size,
            # "modified_at": file_obj.modified_at,
            "children": []
        }

        children = FileObject.objects.filter(parent=file_obj, trashed_at__isnull=True).order_by('type', 'name')
        for child in children:
            if child.type == 'folder':
                node['children'].append(self.build_file_tree(child))
            else:
                node['children'].append({
                    "uid": str(child.uid),
                    "name": child.name,
                    "type": child.type,
                    # "uploaded_url": child.uploaded_url,
                    # "size": child.size,
                    # "modified_at": child.modified_at,
                })

        return node
