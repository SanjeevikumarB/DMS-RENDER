# accounts/urls.py
from django.urls import path
from accounts.views.google_oauth_views import GoogleOAuthView
from accounts.views.user_views import RegisterView, LoginView, RefreshTokenView
from accounts.views.user_views import AccessTokenVerifyView, LogoutView
from accounts.views.admin_views import CreateUserByAdminView, CreateClientAdminView
from accounts.views.admin_views import JoinRequestListView, JoinRequestReviewView
from accounts.views.user_management_views import ChangePasswordView, DeleteAccountOTPRequestView, DeleteAccountView, DeleteClientAdminView, MeView, RoleEditRequestCreateView, SetPasswordConfirmView, SetPasswordRequestOTPView, SetPasswordVerifyOTPView
from accounts.views.user_management_views import RoleEditRequestReviewView, DeleteRegularUserView, RoleEditRequestListView
from accounts.views.notifications_views import NotificationListView, MarkNotificationReadView
from accounts.views.notifications_views import UnreadNotificationListView, MarkAllNotificationsReadView
from accounts.views.notifications_views import MarkNotificationUnreadView, DeleteNotificationView
from accounts.views.notifications_views import ClearAllNotificationsView
from accounts.views.user_management_views import PasswordResetRequestOTPView, PasswordResetVerifyOTPView, PasswordResetConfirmView
urlpatterns = [
    # Authentication
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path("oauth/google/", GoogleOAuthView.as_view(), name="google-oauth"),
    path('token/refresh/', RefreshTokenView.as_view(), name='refresh'),
    path('token/verify/', AccessTokenVerifyView.as_view(), name='token-verify'),
    path("logout/", LogoutView.as_view(), name="logout"),
    
    # Admin
    path('admin/create-user/', CreateUserByAdminView.as_view(), name='admin-create-user'),
    path('admin/create-client-admin/', CreateClientAdminView.as_view(), name='create-client-admin'),
    path("admin/client-admins/<uuid:uid>/", DeleteClientAdminView.as_view(), name="delete-client-admin"),
    path('admin/join-requests/', JoinRequestListView.as_view(), name='join-request-list'),
    path('admin/join-requests/<uuid:uid>/review/', JoinRequestReviewView.as_view(), name='join-request-review'),
    
    # User Management
    path("me/", MeView.as_view(), name="user-profile"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path('role-requests/', RoleEditRequestCreateView.as_view(), name='create-role-request'),
    path("admin/role-requests/", RoleEditRequestListView.as_view(), name="role-request-list"),
    path("admin/role-requests/<uuid:uid>/review/", RoleEditRequestReviewView.as_view(), name="review-role-request"),
    path("users/<uuid:uid>/", DeleteRegularUserView.as_view(), name="delete-regular-user"),
    # Forget Password
    path("auth/request-password-reset/", PasswordResetRequestOTPView.as_view(), name='request-password-reset'),
    path("auth/verify-password-reset-otp/", PasswordResetVerifyOTPView.as_view(), name='verify-password-reset'),
    path("auth/confirm-password-reset/", PasswordResetConfirmView.as_view(), name='confirm-password-reset'),
    # Set Password
    path('set-password/request-otp/', SetPasswordRequestOTPView.as_view(), name='set-password-request-otp'),
    path('set-password/verify-otp/', SetPasswordVerifyOTPView.as_view(), name='set-password-verify-otp'),
    path('set-password/confirm/', SetPasswordConfirmView.as_view(), name='set-password-confirm'),
    # delete/me
    path("delete/me/request-otp/", DeleteAccountOTPRequestView.as_view(), name="delete_account_request_otp"),
    path("delete/me/", DeleteAccountView.as_view(), name="delete_account"),
    
    # notification
    path("notifications/", NotificationListView.as_view(), name="notification-list"),
    path("notifications/<uuid:uid>/mark-read/", MarkNotificationReadView.as_view(), name="mark-notification-read"),
    path("notifications/unread/", UnreadNotificationListView.as_view(), name="unread-notifications"),
    path("notifications/mark-all-read/", MarkAllNotificationsReadView.as_view(), name="mark-all-notifications-read"),
    path("notifications/<uuid:uid>/mark-unread/", MarkNotificationUnreadView.as_view(), name="mark-notification-unread"),
    path("notifications/<uuid:uid>/", DeleteNotificationView.as_view(), name="delete-notification"),
    path("notifications/clear-all/", ClearAllNotificationsView.as_view(), name="clear-all-notifications"),
]
