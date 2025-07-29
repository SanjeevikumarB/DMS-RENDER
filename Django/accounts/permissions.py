from rest_framework.permissions import BasePermission

class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_superuser


class IsClientAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_client_admin


class IsRegularUser(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_regular_user 


class IsAuthenticatedOnly(BasePermission):
    """
    Use this to ensure the user is authenticated, regardless of role.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
