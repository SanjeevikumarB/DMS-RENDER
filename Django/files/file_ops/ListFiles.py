# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework.permissions import IsAuthenticated
# from accounts.authentication import CustomJWEAuthentication
# from files.models import FileObject, StarredFile

# class ListUserFilesAPIView(APIView):
#     authentication_classes = [CustomJWEAuthentication]
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         user = request.user
#         root_files = FileObject.objects.filter(owner=user, parent=None, trashed_at__isnull=True).order_by('type', 'name')
#         # data = [self.build_file_tree(obj) for obj in root_files]
#         starred_uids = set(str(uid) for uid in StarredFile.objects.filter(user=user).values_list('file__uid', flat=True))
        
#         data = [self.build_file_tree(obj, starred_uids) for obj in root_files]
#         return Response(data)

#     def build_file_tree(self, file_obj, starred_uids):
#         node = {
#             "uid": str(file_obj.uid),
#             "name": file_obj.name,
#             "type": file_obj.type,
#             "is_starred": str(file_obj.uid) in starred_uids
#         }

#         if file_obj.type == "folder":
#             children = FileObject.objects.filter(parent=file_obj).order_by('type', 'name')
#             node["children"] = [self.build_file_tree(child, starred_uids) for child in children]

#         return node

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from accounts.authentication import CustomJWEAuthentication
from files.models import FileObject, StarredFile

class ListUserFilesAPIView(APIView):
    authentication_classes = [CustomJWEAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        root_files = FileObject.objects.filter(
            owner=user, parent=None, trashed_at__isnull=True
        ).order_by('type', 'name')

        starred_uids = set(
            str(uid) for uid in StarredFile.objects.filter(user=user).values_list('file__uid', flat=True)
        )

        data = [self.build_file_tree(obj, starred_uids) for obj in root_files]
        return Response(data)

    def build_file_tree(self, file_obj, starred_uids):
        path_list = self.get_path_list(file_obj)
        node = {
            "uid": str(file_obj.uid),
            "name": file_obj.name,
            "type": file_obj.type,
            "is_starred": str(file_obj.uid) in starred_uids,
            "breadcrumbs": path_list,                      # List of folder/file names from root
            "path": "/" + "/".join(path_list)              # String path from root
        }

        if file_obj.type == "folder":
            children = FileObject.objects.filter(parent=file_obj, trashed_at__isnull=True).order_by('type', 'name')
            node["children"] = [self.build_file_tree(child, starred_uids) for child in children]

        return node

    def get_path_list(self, file_obj):
        path = []
        current = file_obj
        while current:
            path.insert(0, current.name)
            current = current.parent
        return path

