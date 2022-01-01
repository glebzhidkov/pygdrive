from __future__ import annotations

import io
import mimetypes
import os
from typing import Optional, Union

from google.auth.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload, MediaIoBaseUpload

from .typed import ContentTypes, Corpora, ResponseDict, Space


class DriveApi:
    """
    Google Drive API v3 wrapper.

    See also: [API reference](https://developers.google.com/drive/api/v3/reference).
    """
    FILE_ATTRS = (
        "id, name, mimeType, description, parents, trashed, starred, contentRestrictions, "
        "webViewLink, createdTime, modifiedTime, quotaBytesUsed"
    )
    PERMISSION_ATTRS = "id, type, role, emailAddress, displayName, expirationTime"
    CHUNK_SIZE = 1000
    RESUMABLE_UPLOAD = True

    def __init__(self, creds: Credentials, search_page_size: int = 100):
        self.creds = creds
        self.service = build("drive", "v3", credentials=creds)
        self.search_page_size = search_page_size
        assert 0 < self.search_page_size < 1001

    def get_file(self, file_id: str, attrs=None) -> ResponseDict:
        return (
            self.service.files()
            .get(fileId=file_id, fields=attrs or self.FILE_ATTRS)
            .execute()
        )

    def create_file(self, metadata: ResponseDict) -> ResponseDict:
        return (
            self.service.files().create(body=metadata, fields=self.FILE_ATTRS).execute()
        )

    def update_file(
        self, file_id: str, metadata: ResponseDict = None, **kwargs
    ) -> ResponseDict:
        return (
            self.service.files()
            .update(fileId=file_id, body=metadata, **kwargs)
            .execute()
        )

    def delete_file(self, file_id: str) -> None:
        self.service.files().delete(fileId=file_id).execute()

    def empty_trash(self) -> None:
        self.service.files().emptyTrash().execute()

    def list_files(
        self,
        query: str,
        corpora: Corpora = "user",
        space: Space = "drive",
        drive_id: Optional[str] = None,
        order_by: Optional[str] = None,
        next_page_token: Optional[str] = None,
    ) -> ResponseDict:
        """
        https://developers.google.com/drive/api/v3/reference/files/list
        """
        return (
            self.service.files()
            .list(
                q=query,
                corpora=corpora,
                driveId=drive_id,
                orderBy=order_by,
                pageSize=self.search_page_size,
                pageToken=next_page_token,
                spaces=space,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                fields=f"files({self.FILE_ATTRS})",
            )
            .execute()
        )

    def export_file(self, file_id: str, mime_type: str):
        return self.service.files().export(fileId=file_id, mimeType=mime_type)

    def update_file_media(
        self, content: ContentTypes, file_id: str, mime_type: str
    ) -> ResponseDict:
        media = self._prepare_media_for_upload(content=content, mime_type=mime_type)
        media.stream()
        request = self.service.files().update(fileId=file_id, media_body=media)

        response = None
        while not response:
            status, response = request.next_chunk()
        return response

    def upload_file_media(
        self, content: ContentTypes, title: str, parent_id: Optional[str]
    ) -> ResponseDict:

        file_metadata = {}
        if parent_id:
            file_metadata["parents"] = [parent_id]

        if isinstance(content, str) and os.path.isfile(content):
            mime_type = mimetypes.guess_type(content)[0]
            file_metadata["name"] = os.path.basename(content)
        else:
            mime_type = mimetypes.guess_type(title)[0]
            file_metadata["name"] = title

        assert mime_type is not None
        media = self._prepare_media_for_upload(content=content, mime_type=mime_type)
        media.stream()

        request = self.service.files().create(
            body=file_metadata, media_body=media, fields=self.FILE_ATTRS
        )

        response = None
        while not response:
            status, response = request.next_chunk()
        return response

    def _prepare_media_for_upload(self, content: ContentTypes, mime_type: str):

        if isinstance(content, str) and os.path.isfile(content):
            return MediaFileUpload(
                filename=content,
                mimetype=mime_type,
                chunksize=self.CHUNK_SIZE,
                resumable=self.RESUMABLE_UPLOAD,
            )

        if isinstance(content, str):
            content = content.encode("utf-8")

        if isinstance(content, bytes):
            content = io.BytesIO(content)

        if isinstance(content, io.BytesIO) or hasattr(content, "seek"):
            return MediaIoBaseUpload(
                fd=content,
                mimetype=mime_type,
                chunksize=self.CHUNK_SIZE,
                resumable=self.RESUMABLE_UPLOAD,
            )

        raise Exception

    def download_file_media(
        self, file_id: str, path: Optional[str], export_format: Optional[str]
    ) -> Union[io.BytesIO, io.FileIO]:
        """
        response.getvalue() -> bytes
        fh.getvalue().decode("utf-8") -> string
        """
        if export_format:
            request = self.service.files().export_media(
                fileId=file_id, mimeType=export_format
            )
        else:
            request = self.service.files().get_media(fileId=file_id)

        fh = io.FileIO(path, "wb") if path else io.BytesIO()

        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            _, done = downloader.next_chunk()

        return fh

    def copy_file(self, file_id: str, title: str, parent_id: str) -> ResponseDict:

        copy_id = (
            self.service.files()
            .generateIds(space="drive", count=1)
            .execute()
            .get("ids")[0]
        )
        meta = {"id": copy_id, "parents": [parent_id], "name": title}
        new_file = self.service.files().copy(fileId=file_id, body=meta).execute()

        return self.get_file(file_id)  # reduce the extra call?

    def create_shortcut(self, file_id: str, title: str, parent_id: str) -> ResponseDict:

        meta = {
            "parents": [parent_id],
            "name": title,
            "mimeType": "application/vnd.google-apps.shortcut",
            "shortcutDetails": {"targetId": file_id},
        }
        return self.service.files().create(body=meta).execute()
        # likely returns wrong contents though

    def create_permission(self, file_id: str, body: ResponseDict) -> ResponseDict:
        return (
            self.service.permissions()
            .create(fileId=file_id, fields=self.PERMISSION_ATTRS, body=body)
            .execute()
        )

    def delete_permission(self, file_id: str, permission_id: str) -> None:
        self.service.permissions().delete(
            fileId=file_id, permissionId=permission_id
        ).execute()

    def update_permission(
        self, file_id: str, permission_id: str, body: ResponseDict, **kwargs
    ) -> ResponseDict:
        return (
            self.service.permissions()
            .update(
                fileId=file_id,
                permissionId=permission_id,
                fields=self.PERMISSION_ATTRS,
                body=body,
                **kwargs,
            )
            .execute()
        )
