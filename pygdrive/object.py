from __future__ import annotations

import webbrowser
from typing import Union, TYPE_CHECKING, Optional, Dict, List

from pygdrive.utils import mimes_to_types, FOLDER_TYPE, FILE_ATTRS
from pygdrive.exceptions import NotAFolder

if TYPE_CHECKING:
    from pygdrive.client import DriveClient
    from pygdrive.folder import DriveFolder
    from pygdrive.file import DriveFile


class DriveObject:
    """Base class for `DriveFile` and `DriveFolder`"""

    def __init__(self, 
            client: DriveClient, 
            file_id: str, 
            title: str, 
            mime_type: str, 
            parent_id: str,
            trashed: bool,
            starred: bool
            ) -> None:
        
        self.client = client
        self.__id = file_id
        self.__title = title
        self.__mime_type = mime_type
        self.__parent_id = 'root' if not parent_id else parent_id
        self.__trashed = trashed
        self.__starred = starred

        self.__killed = False
        self._needs_sync = False
        self.__permissions = {}

    def __repr__(self):
        return self._repr(self.client.REPR_CONTENT) + '\n\n'

    def _repr(self, deep: bool = False) -> str:
        r = ''
        if self.__trashed: r += 'DELETED '
        if self.__killed: r += 'IRREVERSABLY '
        r += 'DriveFolder: ' if self.mime_type == FOLDER_TYPE else 'DriveFile: '
        r += self.__title

        if deep and self.mime_type == FOLDER_TYPE:
            for obj in self.content: # pylint: disable=no-member
                r += f'\n -> {obj._repr(False)}'
        return r

    def __eq__(self, other):
        return self.__id == other.__id

    def __len__(self):
        if self.mime_type == FOLDER_TYPE:
            return len(self.content) # pylint: disable=no-member
        else:
            return 0

    def sync(self) -> None:
        attrs = self.get_attributes(FILE_ATTRS)

        self.__title = attrs.get('name')
        #self.__parent_id = 'root' if not parents else file_object.get('parents')[0]
        self.__trashed = attrs.get('trashed')
        self.__starred = attrs.get('starred')

        if self.__mime_type == FOLDER_TYPE:
            self._files = list(self.client.search(query=f"'{self.id}' in parents and trashed = false"))
        # update trashed; title; parents
        self._needs_sync = False

    @property
    def id(self) -> str:
        """Google Drive ID of this file or folder (immutable)"""
        return self.__id
    
    @property
    def url(self) -> str:
        """Link to this file or folder"""
        if self.__mime_type == FOLDER_TYPE:
            return f"https://drive.google.com/drive/u/1/folders/{self.id}"
        else:
            return f"https://drive.google.com/file/d/{self.id}"

    def open_in_browser(self) -> None:
        """Open this file or folder in default system browser"""
        webbrowser.open_new_tab(self.url)

    @property
    def mime_type(self) -> str:
        """The mime type of this file or folder (immutable)"""
        return self.__mime_type

    @property
    def title(self) -> str:
        """Title of this file or folder"""
        if self._needs_sync: self.sync()
        return self.__title
    
    @title.setter
    def title(self, new_title: str) -> None:
        self.set_attributes({'name': new_title})
        self.__title = new_title

    @property
    def parent(self) -> DriveFolder:
        """Returns the `DriveFolder` where this file or folder is stored"""
        if self._needs_sync: self.sync()
        return self.client._object_maker({'id' :self.__parent_id})

    @parent.setter
    def parent(self, new_parent: Union[DriveFolder, str]) -> None:
        self.move(new_parent)

    def move(self, new_parent: Union[DriveFolder, str]) -> None:
        """Moves file to a different parent folder, `new_parent`, specified by its ID or an instance of `DriveFolder`"""
        new_parent = isolate_folder_id(new_parent)
        file = self.client.service.files().get(fileId=self.id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents'))
        self.client.service.files().update(fileId=self.id, addParents=new_parent, removeParents=previous_parents).execute()
        self.__parent_id = new_parent

        for prev_parent in previous_parents:
            self.client._desync_object(prev_parent)
    
    @property
    def is_trashed(self) -> bool:
        if self._needs_sync: self.sync()
        return self.__trashed

    @is_trashed.setter
    def is_trashed(self, new_value: bool) -> None:
        if self.is_trashed != new_value:
            self.set_attributes({'trashed': new_value})
            self.__trashed = new_value

    @property
    def is_starred(self) -> bool:
        if self._needs_sync: self.sync()
        return self.__starred

    @is_starred.setter
    def is_starred(self, new_value: bool) -> None:
        if self.is_starred != new_value:
            self.set_attributes({'starred': new_value})
            self.__starred = new_value

    def delete(self, skip_bin: bool = False) -> None:
        """Puts the file into Trash (default) or deletes it from Drive permanently"""
        self.client._desync_object(self.__parent_id)
        self.__trashed = True

        if self.mime_type == FOLDER_TYPE:
            for obj in self.content: #pylint: disable=no-member
                self.client._desync_object(obj.id)

        if not skip_bin:
            self.set_attributes({'trashed': True})
            self.client.logger.info(f"'{self.title}' was moved to the trash and can be restored within 30 days.")
        else:
            self.client.service.files().delete(fileId=self.__id).execute()
            self.__killed = True
            self.client.logger.info(f"'{self.title}' was irreversably deleted.")

    def restore(self) -> None:
        """Restores file from the trash bin"""
        self.client._desync_object(self.__parent_id)
        self.__trashed = True
        self.set_attributes({'trashed', False})

    def share(self, with_: str, role: str) -> None:
        """Share this file or folder with a user or a domain
        
        Args:
            with_       Email address or domain (user@example.com; example.com) or 'anyone'
            role        'reader', 'commenter', or 'writer'

        Note: role = 'owner' is possible, see however https://stackoverflow.com/questions/62699404/how-to-update-permissions-in-google-drive-api-v3
        """
        if role not in ('reader', 'writer', 'commenter', 'organizer', 'owner'):
            raise ValueError(f"role '{role}' is not accepted")
        if with_ == 'anyone':
            permission = {'type': 'anyone', 'role': role}
        if '@' in with_:
            permission = {'type': 'user', 'role': role, 'emailAddress': with_}
        else:
            permission = {'type': 'domain', 'role': role, 'domain': with_}
        if role == 'owner':
            print(f'Changing owner of DriveFile {self.__id}')
            permission['transerOwnership'] = True

        self.client.service.permissions().create(fileId=self.__id, body=permission)

    def get_permissions(self) -> List[Dict[str, str]]:
        """Get a list of dictionaries with file/folder permissions. Keys: `with_, role, type, id` """
        response = self.client.service.permissions().list(fileId=self.__id).get('permissions')
        self.__permissions = [{'with': permission['emailAddress'], 
                               'role': permission['role'],
                               'type': permission['type'],
                               'id': permission['id']} 
                              for permission in response]
        return self.__permissions

    def remove_permission(self, from_: str) -> None:
        """Remove a file/folder permission from a user or domain"""
        if not self.__permissions: self.get_permissions()
        permission_id = [permission['id'] for permission in self.__permissions if permission['with'] == from_][0]
        if not permission_id:
            print(f'failed at removing permission for {from_} because no permission was found')
        else:
            self.client.service.permissions().delete(fileId=self.__id, permissionId=permission_id).execute()

    def set_permissions(self, permissions: List[Dict[str, str]], override: bool = False) -> None:
        """Set `permissions`, e.g. based on permissions of a different file. Use `override` to remove old permissions."""
        # lazy implementation
        if override:
            if not self.__permissions: self.get_permissions()
            for old_permission in self.__permissions:
                self.remove_permission(old_permission['with'])
        
        for new_permission in permissions:
            self.share(with_=new_permission['with'], role=new_permission['role'])

    def get_attributes(self, attrs: str) -> dict: 
        # https://developers.google.com/drive/api/v3/reference/files
        return self.client.service.files().get(fileId=self.id, fields=attrs).execute()

    def set_attributes(self, attrs: dict) -> None:
        return self.client.service.files().update(fileId=self.id, body=attrs).execute()

    def create_shortcut(self, 
            parent: Union[DriveFolder, str],
            title: Optional[str] = None
            ) -> DriveFile:
        """Creates a shortcut to this file and returns the `DriveFile` of the shortcut

        Args:
            parent      ID or DriveFolder instance of the new parent folder
            title       Shortcut title (if not specified, 
                        'Shortcut to %title' is used)
        """
        parent = isolate_folder_id(parent)
        title = title or f'Shortcut to {self.title}'

        meta = {
            'parents': [parent], 
            'name': title, 
            'mimeType': 'application/vnd.google-apps.shortcut',
            'shortcutDetails': {'targetId': self.id
            }}
        new_file = self.client.service.files().create(body=meta).execute()

        self.client._desync_object(parent)

        return self.client._object_maker(new_file)


def isolate_folder_id(folder: Union[DriveFolder, str]) -> str:
    """ """
    if isinstance(folder, DriveObject):
        if folder.mime_type == FOLDER_TYPE:
            return folder.id
    elif isinstance(folder, str):
        return folder
    else:
        raise ValueError()
        