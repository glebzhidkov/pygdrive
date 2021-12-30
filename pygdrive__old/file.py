
from __future__ import annotations

import io
import os
import warnings
import webbrowser
import mimetypes
from typing import List, Optional, TYPE_CHECKING, Union

from pygdrive__old.streamer import streamer_upload_file, streamer_download_file, MediaIoBaseDownload

from pygdrive__old.object import DriveObject, isolate_folder_id
from pygdrive__old.folder import DriveFolder

from pygdrive__old.utils import mimes_to_types
from pygdrive__old import exceptions
from pygdrive__old.exceptions import valid_api_request


class DriveFile(DriveObject):
    """A Google Drive file"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def is_google_doc(self) -> bool:
        return self.mime_type.startswith('application/vnd.google-apps.')

    def download(self, 
            target_path: Optional[str] = '', 
            export_format: Optional[str] = None,
            to_string: Optional[bool] = False,
            to_bytes: Optional[bool] = False
            ) -> Optional[bytes]:
        """Downloads this file to folder or bytes

        Args:
            target_path     folder where the file is saved (ignored if to_bytes=True)
                            (WARNING: silently overwritten if exists) # TODO
            export_format   export format (mime type) for Google Documents 
                            (if not specified, using 
                            DriveClient.EXPORT_DEFAULT = 'application/pdf')
            to_string       return string? (default False; higher importance)
            to_bytes        return bytes? (default False; lower importance)

        Returns: None or file bytes or file string
        """

        if not export_format:
            export_format = self.client.EXPORT_DEFAULT

        if self.is_google_doc:
            request = self.client.service.files().export_media(
                fileId=self.id, mimeType=export_format)
            target_path = os.path.join(
                target_path, 
                self.title + mimetypes.guess_extension(export_format))
        else:
            request = self.client.service.files().get_media(fileId=self.id)
            target_path = os.path.join(target_path, self.title)

        if to_bytes or to_string:
            fh = io.BytesIO()
        else:
            fh = io.FileIO(target_path, 'wb')
        
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            _, done = downloader.next_chunk()

        if to_bytes:
            return fh.getvalue()
        if to_string:
            return fh.getvalue().decode('utf-8')

    def update(self, **kwargs) -> None:
        """Updates this file with new content from `path`, `string`, or `bytes_`

        WARNING: the type of the file may not change! To change the type, upload a new file.

        Args:
            path        file location (name and mime type will be inherited 
                        from the file title, unless title is specified)
            title       title of the file (e.g., 'note.txt' or 'drawing.png'),
                        from which the mime type will be inherited
                        (REQUIRED if uploading file from string or bytes)
            string      file string
            bytes_      file bytes

            resumable   file can be uploaded in chunks? default True
            chunk_size  chunk size (defaults to drive.DEFAULT_CHUNK_SIZE = 10*1024*1024)
                        minimum is 1024*1024
            progress    show progress bar? default True
        """
        _ = streamer_upload_file(__client=self.client, __drive_file=self, **kwargs)

    def copy(self, 
             new_parent: Optional[Union[DriveFolder, str]] = None, 
             new_title: Optional[str] = None) -> DriveFile:
        """Creates a copy of this file and returns the new `DriveFile`
        
        Args:
            new_parent  ID or DriveFolder instance of the new parent folder (if not specified, inherited from the original)
            new_title   New file title (if not specified, same as the original title)
        """
        new_parent = isolate_folder_id(new_parent or self.parent)
        new_title = new_title or self.title

        response = self.client.service.files().generateIds(space='drive', count=1).execute()
        new_id = response.get('ids')[0]

        meta = {'id': new_id, 'parents': [new_parent], 'name': new_title}
        new_file = self.client.service.files().copy(fileId=self.id, body=meta).execute()

        self.client._desync_object(self.parent.id)
        self.client._desync_object(new_parent)

        return self.client._object_maker(new_file)
