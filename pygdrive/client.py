""" """

# disable errors resulting from self.service
# pylint: disable=no-member

import os
import io
import logging
import warnings
import mimetypes
from typing import List, Optional, Union, Tuple

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload, MediaIoBaseUpload

from pygdrive.folder import DriveFolder
from pygdrive.file import DriveFile
from pygdrive.utils import FOLDER_TYPE, types_to_mimes, FILE_ATTRS
from pygdrive.exceptions import FileNotFound, NotAFolder


class DriveClient:
    """Client for Google Drive API v3
    https://developers.google.com/drive/api/v3/about-sdk

    Open an existing file by ID or title:
    ```
        gdrive = pygdrive.authenticate('creds.json')
        file = gdrive[id]
        file = gdrive.find_file(title=title, parent=parent)[0]
    ```
        
    Upload a new file to the base folder:
    ```
        new_file = gdrive.root.upload_file(path=path)
        type(gdrive.root) # DriveFolder
        type(new_file) # DriveFile
    ```

    Or to any other folder:
    ```
        mess_folder = gdrive.find_folder('mess')[0]
        new_file = mess_folder.upload_file_from_string(string=string, title=title)
    ```
    """

    def __init__(self, creds) -> None:
        self.service = build('drive', 'v3', credentials=creds)
        self.logger = logging.getLogger('pygdrive')
        self.session = {} # stores all DriveObject's loaded in the current session

        self.DEFAULT_CHUNK_SIZE = 10 * 1024 * 1024
        self.EXPORT_DEFAULT = 'application/pdf'
        self.PARENTS_WARNING = True
        self.ROOT = 'root'
        self.REPR_CONTENT = False

    def __getitem__(self, key) -> None:
        return self._object_maker({'id': key})

    def _desync_object(self, object_id: str) -> None:
        """ """
        if object_id in self.session:
            self.session[object_id]._needs_sync = True
            logging.info('needs_sync updated')
        else:
            logging.info('else')

    def _object_maker(self, file_object: dict) -> Union[DriveFile, DriveFolder]:
        """ Makes a `DriveFile` or `DriveObject` from object attributes in a dictionary-like input

        Minimal required call is: `gdrive._object_maker({'id': '%ID'})`.

        If an object with `id` has already been accessed in the current session,
        its instance is returned.

        If all possible attributes (`id`, `name`, `mimeType`, `parents`, `trashed`)
        are present, an object is instantly returned. If some value is missing, the object
        information is (possibly, repeatedly) pulled via Google Drive API.
        """

        ATTRIBUTES = FILE_ATTRS.replace(' ', '').split(',')

        DO_QUERY = any([attr not in file_object.keys() for attr in ATTRIBUTES])

        file_id = file_object.get('id', None)
        attrs = {'file_id': file_id}

        if not file_id:
            logging.error('pygdrive object_maker: Failed to get file_id')
            raise ValueError

        if file_id in self.session:
            return self.session[file_id]

        if DO_QUERY:
            file_object = self.service.files().get(fileId=file_id, fields=FILE_ATTRS).execute()

        parents = file_object.get('parents', [])
        if len(parents) > 1 and self.PARENTS_WARNING:
            logging.warning(
                f'File {file_id} has more than 1 parents, they will be removed once file will be moved.'
                f'Set `gdrive.PARENTS_WARNING = False` to hide this warning')

        file_id = file_object.get('id')
        attrs['title'] = file_object.get('name')
        attrs['mime_type'] = file_object.get('mimeType')
        attrs['parent_id'] = 'root' if not parents else file_object.get('parents')[0]
        attrs['trashed'] = file_object.get('trashed', False)
        attrs['starred'] = file_object.get('starred', False)

        # create new object
        if attrs['mime_type'] == FOLDER_TYPE:
            self.session[file_id] = DriveFolder(self, **attrs)
        else:
            self.session[file_id] = DriveFile(self, **attrs)

        return self.session[file_id]

    def search(self, query: str) -> Tuple[Union[DriveFile, DriveFolder]]:
        # TODO: next page
        """Searches for Google Drive files and folders with a custom query

        Args:
            query   see https://developers.google.com/drive/api/v3/search-files
        
        Returns: a list consisting of `DriveFile`'s and `DriveFolder`'s
        """
        
        response = self.service.files().list(
            q=query,
            spaces='drive',
            fields=f'files({FILE_ATTRS})').execute().get('files', [])

        return tuple(self._object_maker(file_obj) for file_obj in response)

    def find_file(self,
                  title: Optional[str] = None, 
                  parent: Optional[Union[str, DriveFolder]] = None, 
                  file_type: Optional[str] = None, 
                  approximate: bool = False
                  ) -> List[DriveFile]:
        """Search for a file on Google Drive
        
        Args (all are optional):
            title:          full or partial title of the file
            parent:         id of the parent folder or its DriveFolder instance
            file_type:      (mime) type of the file
            approximate:    True for partial title matches (default is False)

        Returns: a list of `DriveFile`'s 
        """
        query = [f"mimeType != '{FOLDER_TYPE}'"]
        
        if title and approximate:
            query.append(f"name contains '{title}'")
        if title and not approximate:
            query.append(f"name = '{title}'")
        if file_type:
            query.append(f"mimeType = '{types_to_mimes(file_type)}'")
        if isinstance(parent, DriveFolder):
            parent = parent.id
        if parent:
            query.append(f"'{parent}' in parents")

        return self.search(' and '.join(query))

    def find_folder(self,
                    title: Optional[str] = None, 
                    parent: Optional[Union[str, DriveFolder]] = None, 
                    file_type: Optional[str] = None, 
                    approximate: bool = False
                    ) -> List[DriveFolder]:
        """Search for a folder on Google Drive
        
        Args (all are optional):
            title:          full or partial title of the file
            parent:         id of the parent folder or its DriveFolder instance
            type:           (mime) type of the file
            approximate:    True for partial title matches (default is False)

        Returns: a list of `DriveFolder`s
        """
        query = [f"mimeType = '{FOLDER_TYPE}'"]
        
        if title and approximate:
            query.append(f"name contains '{title}'")
        if title and not approximate:
            query.append(f"name = '{title}'")
        if file_type:
            query.append(f"mimeType = '{types_to_mimes(file_type)}'")
        if isinstance(parent, DriveFile):
            if not parent.is_folder:
                raise NotAFolder(f'{parent.title} provided as a parent is not a folder.')
            parent = parent.id
        if parent:
            query.append(f"'{parent}' in parents")

        return self.search(' and '.join(query))

    def find_or_create_folder(self, title: str, parent: Optional[str] = None) -> DriveFile:
        """Searches for a folder and returns the best match or creates one, if it does not exist

        Args:
            title           title of the folder
            parent          ID of the parent folder

        Returns: DriveFile

        Warning is issued if more than one such folder exist.
        """
        parent = parent or self.ROOT
        search = self.find_folder(title=title, parent=parent)

        if len(search) > 1:
            warnings.warn("More than one folder with title={title} and parent={parent} found, first returned")

        if search:
            return search[0]
        else:
            return self[parent].create_subfolder(title=title)

    @property
    def root(self) -> DriveFolder:
        """Access root (base) folder of Google Drive. Returns `DriveFolder`"""
        root_folder = self._object_maker({'id': self.ROOT})
        self.ROOT = root_folder.id # update with the actual id
        return root_folder

    @property
    def bin(self) -> Tuple[Union[DriveFile, DriveFolder]]:
        """Returns a tuple with objects in the bin"""
        return self.search(query='trashed = true')

    @property 
    def starred(self) -> List[Union[DriveFile, DriveFolder]]:
        """Returns a tuple with starred objects"""
        return self.search(query='starred = true')

    def empty_bin(self) -> None:
        """Deletes all files from the bin"""
        # https://developers.google.com/drive/api/v3/reference/files/emptyTrash
        trashed_files = self.bin
        for obj in trashed_files:
            obj.delete(to_trash=False)
        logging.info(f'Irreversably deleted {len(trashed_files)} files from the bin.')

    def build_tree(
            self, 
            start_from: Optional[DriveFolder] = None, 
            include_files: bool = False,
            depth: Optional[int] = None
            ) -> dict:
        """ """

        def deepen_folder_tree(start_folder: DriveFolder) -> List[Tuple[DriveFolder, List]]:
            return [(folder, deepen_folder_tree(folder)) for folder in start_folder.subfolders]
        
        def deepen_contents_tree(start_folder: DriveFolder) -> List[Tuple[DriveFolder, List]]:
            return [(obj, deepen_contents_tree(obj) if isinstance(obj, DriveFolder) else None) for obj in start_folder.contents]

        if not start_from:
            start_from = self.root
        
        if include_files:
            return deepen_contents_tree(start_from)
        else:
            return deepen_folder_tree(start_from)
