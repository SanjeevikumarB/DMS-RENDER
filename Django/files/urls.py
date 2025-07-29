# files/urls.py
from django.urls import path
from .file_ops.Upload import MultiFileUploadAPIView
from .file_ops.ListFiles import ListUserFilesAPIView
from .file_ops.CreateFolder import CreateFolderAPIView
from .file_ops.RenameFileOrFolder import RenameFileOrFolderAPIView
from .file_ops.Move import MoveFileOrFolderAPIView
from .file_ops.starred.star import ToggleStarAPIView
from .file_ops.starred.favorites import FavoritesListAPIView
from .file_ops.version.ViewVersions import ListFilesVersionView
from .file_ops.Download import DownloadFileAPIView
from .file_ops.version.FileInfo import FileInfoAPIView
from .file_ops.version.RestoreVersion import RestoreVersionAPIView
from .file_ops.version.SaveCopy import SaveAsCopyAPIView
# from .file_ops.trash import TrashFileOrFolderAPIView

urlpatterns = [
    path('upload/', MultiFileUploadAPIView.as_view(), name='file-upload'),
    path('create-folder/', CreateFolderAPIView.as_view(), name='create-folder'),
    path('list-files/', ListUserFilesAPIView.as_view(), name='list-files'),
    path('rename/', RenameFileOrFolderAPIView.as_view(), name='rename'),
    path('move/', MoveFileOrFolderAPIView.as_view(), name='move'),  
    path('toggle-star/', ToggleStarAPIView.as_view(), name='toggle-star'),
    path('favorites/', FavoritesListAPIView.as_view(), name='favorites'),
    path('versions/', ListFilesVersionView.as_view(), name='list-file-versions'),
    path('download/', DownloadFileAPIView.as_view(), name='download-file'),
    path('file-info/<uuid:file_uid>/', FileInfoAPIView.as_view(), name='file-info'),
    path('restore-version/', RestoreVersionAPIView.as_view(), name='restore-version'),
    path('save-as-copy/', SaveAsCopyAPIView.as_view(), name='save-as-copy'),
    # path('trash/', TrashFileOrFolderAPIView.as_view(), name='trash'),
]
