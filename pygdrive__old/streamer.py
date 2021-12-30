
from __future__ import annotations

import mimetypes
import os
import io

from math import ceil
from tqdm import tqdm
from typing import Optional, TYPE_CHECKING

from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload, MediaIoBaseUpload

from pygdrive__old.utils import FILE_ATTRS

if TYPE_CHECKING:
    from pygdrive__old.file import DriveFile


def streamer_upload_file(
        __client = None,
        __drive_file: Optional[DriveFile] = None,
        __parent_id: Optional[str] = None,
        path: Optional[str] = None,
        title: Optional[str] = None,
        string: Optional[str] = None,
        bytes_: Optional[bytes] = None,
        resumable: Optional[bool] = True,
        chunk_size: Optional[str] = None,
        progress: Optional[bool] = True,
        ) -> dict:
    f"""Uploads or updates a file to Google Drive

    Args:
        __client      authenticated pygdrive client
        __drive_file  DriveFile to be updated (if missing, new file uploaded)
        __parent_id   ID of the parent folder (for new files)
        ...
        
    Returns: an instance of `DriveFile`
    """

    chunk_size = int(chunk_size or __client.DEFAULT_CHUNK_SIZE)
    chunk_size = 1024*1024 if chunk_size < 1024*1024 else chunk_size

    # TYPE
    if __drive_file is not None:
        UPDATE = True
    elif __parent_id is not None:
        UPDATE = False
    else:
        raise ValueError(f'upload_file: specify either drive_file or parent_id')
    
    # FILE METAINFO
    if UPDATE:
        mime_type = __drive_file.mime_type
    else:
        file_metadata = {'parents': [__parent_id]}

        if path and not title:
            mime_type = mimetypes.guess_type(path)[0]
            file_metadata['name'] = os.path.basename(path)
        elif title and (path or string or bytes_):
            mime_type = mimetypes.guess_type(title)[0]
            file_metadata['name'] = title
        else:
            raise ValueError('Please specify path OR string/bytes_ and title')

    # FILE MEDIA
    if path:
        media = MediaFileUpload(
            filename=path, 
            mimetype=mime_type, 
            chunksize=chunk_size,
            resumable=resumable
            )
        media.stream() # ?
    elif string or bytes_:
        if string:
            bytes_ = string.encode('utf-8')
        media = MediaIoBaseUpload(
            fd=io.BytesIO(bytes_), 
            mimetype=mime_type, 
            chunksize=chunk_size,
            resumable=resumable
            )
        media.stream() # ?

    # REQUEST
    if UPDATE:
        request = __client.service.files().update(
            fileId=__drive_file.id, 
            media_body=media
            )
    else:
        request = __client.service.files().create(
            body=file_metadata,
            media_body=media,
            fields=FILE_ATTRS
            )
    
    # PROGRESS BAR
    progress = False if not resumable else progress
    if progress:
        nr_chunks = ceil(request.resumable.size() / chunk_size)
        if nr_chunks > 1:
            pbar = tqdm(total=nr_chunks)
            pbar.set_description(f"Uploading {file_metadata['name']}")
        else:
            progress = False
    
    # UPLOADING FILE
    response = None
    while not response:
        status, response = request.next_chunk()
        if progress and status:
            pbar.update(1)

    if progress:
        pbar.close()

    return response

def streamer_download_file(client):
    pass