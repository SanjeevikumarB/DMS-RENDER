from django.urls import path
from sharing.views.Share import ShareFileOrFolderAPIView
from sharing.views.SharedWithMe import SharedWithMeAPIView
from sharing.views.ProcessShareRequest import ProcessShareRequestAPIView
from sharing.views.RequestAccessUpgrade import RequestAccessUpgradeAPIView
from sharing.views.ProcessAccessUpgrade import ProcessAccessUpgradeAPIView

urlpatterns = [
    path('share/', ShareFileOrFolderAPIView.as_view(), name='share-file-folder'),
    path('shared-with-me/', SharedWithMeAPIView.as_view(), name='shared-with-me'),
    path('process-share-request/', ProcessShareRequestAPIView.as_view(), name='process-share-request'),
    path('request-access-upgrade/', RequestAccessUpgradeAPIView.as_view(), name='request-access-upgrade'),
    path('process-access-upgrade/', ProcessAccessUpgradeAPIView.as_view(), name='process-access-upgrade'),
]
