from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.utils import timezone
from accounts.models import CustomUser
from accounts.authentication import CustomJWEAuthentication
from files.models import FileObject
from ..models import FileAccessControl

class ShareFileOrFolderAPIView(APIView):
    authentication_classes = [CustomJWEAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        file_uid = request.data.get("file_uid")
        shares = request.data.get("shares")  # List of {"email", "access_level"}

        if not file_uid or not isinstance(shares, list) or len(shares) == 0:
            return Response({"error": "Invalid request format."}, status=400)

        try:
            file_obj = FileObject.objects.get(uid=file_uid)
        except FileObject.DoesNotExist:
            return Response({"error": "File or folder not found."}, status=404)

        is_owner = file_obj.owner == request.user
        is_editor = FileAccessControl.objects.filter(
            file=file_obj, user=request.user, access_level="editor"
        ).exists()

        if not (is_owner or is_editor):
            return Response({"error": "You do not have permission to share this file or folder."}, status=403)

        results = []

        for share in shares:
            email = share.get("email")
            access_level = share.get("access_level")

            if not email or access_level not in ["viewer", "editor"]:
                results.append({
                    "email": email,
                    "status": "skipped",
                    "message": "Missing email or invalid access level"
                })
                continue

            try:
                user = CustomUser.objects.get(email=email)
            except CustomUser.DoesNotExist:
                results.append({
                    "email": email,
                    "status": "skipped",
                    "message": "User not found"
                })
                continue

            if user == request.user:
                results.append({
                    "email": email,
                    "status": "skipped",
                    "message": "Cannot share with yourself"
                })
                continue

            # Direct share on selected file/folder
            fac, created = FileAccessControl.objects.update_or_create(
                file=file_obj,
                user=user,
                defaults={
                    "access_level": access_level,
                    "granted_by": request.user,
                    "granted_at": timezone.now(),
                    "inherited": False,
                    "inherited_from": None
                }
            )

            # Apply inherited access to children (only if it's a folder)
            if file_obj.type == "folder":
                descendants = self.get_all_descendants(file_obj)
                for child in descendants:
                    # Skip if the child has direct (non-inherited) sharing already
                    existing = FileAccessControl.objects.filter(file=child, user=user, inherited=False).first()
                    if existing:
                        continue

                    # Create or update inherited access
                    FileAccessControl.objects.update_or_create(
                        file=child,
                        user=user,
                        defaults={
                            "access_level": access_level,
                            "granted_by": request.user,
                            "granted_at": timezone.now(),
                            "inherited": True,
                            "inherited_from": file_obj
                        }
                    )

            results.append({
                "email": email,
                "status": "created" if created else "updated",
                "message": f"{access_level.title()} access {'granted' if created else 'updated'}"
            })

        return Response({
            "file_uid": str(file_obj.uid),
            "shared_by": request.user.email,
            "results": results
        }, status=200)

    def get_all_descendants(self, folder):
        """Recursively get all files/folders under a folder."""
        descendants = []
        children = FileObject.objects.filter(parent=folder, trashed_at__isnull=True)
        for child in children:
            descendants.append(child)
            if child.type == "folder":
                descendants.extend(self.get_all_descendants(child))
        return descendants
