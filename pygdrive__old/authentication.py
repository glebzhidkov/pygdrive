
import os
import json
import warnings
from typing import Optional

from google.oauth2 import credentials, service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

from pygdrive__old.client import DriveClient

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
DEFAULT_DIR = '.pygdrive_secrets'


def authenticate(
    client_secret: Optional[str] = None,
    creds_directory: Optional[str] = None,
    creds_env_var: Optional[str] = None,
    service_account_secret: Optional[str] = None,
    creds = None,
    scopes: Optional[list] = []
    ) -> DriveClient:
    """Authenticates pygdrive with one of the available methods

    1) OAuth 2 user authentication
        client_secret           path to the client secret file or the name of the environment variablex
        creds_directory         path to the directory where generated credentials will be stored (default = '.pygdrive_secrets')
        creds_env_var           alternatively, name of the environment variable in which credentials will be stored
        scopes                  custom scopes (optional)

    2) Google Service account
        service_account_secret  path to the service account secret file or the name of the environment variable
        scopes                  custom scopes (optional)

    3) Custom credentials
        creds                   Credentials file

    Returns:
        DriveClient
    """

    if not scopes:
        scopes = SCOPES

    if client_secret:
        return _oauth2_auth(client_secret, creds_directory, creds_env_var, scopes)

    elif service_account_secret:
        return _service_account_auth(service_account_secret, scopes)

    elif creds:
        return DriveClient(creds=creds)

    else:
        raise ValueError('Please specify `client_secret` or `service_account_secret` or `creds`.')


def _oauth2_auth(client_secret, creds_directory, creds_env_var, scopes) -> DriveClient:
    """ authenticates pygrive with a user account """
     
    # Basic folder management
    if creds_directory:
        if not os.path.exists(creds_directory):
            raise ValueError(f'{creds_directory} does not exist')
        creds_path = os.path.join(creds_directory, '.pygdrive_token.json')
    else:
        if not os.path.exists(DEFAULT_DIR):
            os.mkdir(DEFAULT_DIR)
        creds_path = os.path.join(DEFAULT_DIR, '.pygdrive_token.json')

    # Acess credentials from the previous session or create new
    if creds_env_var and creds_env_var in os.environ:
        try:
            env_value = os.environ.get(creds_env_var)
            creds = credentials.Credentials.from_authorized_user_info(info=json.loads(env_value), scopes=scopes)
        except:
            warnings.warn(f'Failed at using previously generated credentials stored in the environment variable {creds_env_var}')
            creds = __oauth2_auth_new(client_secret=client_secret, scopes=scopes)
    elif os.path.exists(creds_path):
        try:
            creds = credentials.Credentials.from_authorized_user_file(filename=creds_path, scopes=scopes)
        except:
            warnings.warn(f'Failed at using previously generated credentials stored in the file {creds_path}')
            creds = __oauth2_auth_new(client_secret=client_secret, scopes=scopes)
    else:
        creds = __oauth2_auth_new(client_secret=client_secret, scopes=scopes)

    # Update credentials, if needed
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            print('pygdrive: Refreshed previously created credentials.')
        except RefreshError:
            creds = __oauth2_auth_new(client_secret=client_secret, scopes=scopes)

    # Remember credentials for the next session
    if creds_env_var:
        os.environ[client_secret] = creds.to_json()
    else:
        with open(creds_path, 'w') as fp:
            json.dump(json.loads(creds.to_json()), fp)

    return DriveClient(creds=creds)


def __oauth2_auth_new(client_secret, scopes) -> None:
    """ """
    if client_secret in os.environ:
        env_value = os.environ.get(client_secret)
        flow = InstalledAppFlow.from_client_config(json.loads(env_value), scopes)
        creds = flow.run_local_server(port=0)
    elif os.path.exists(client_secret):
        flow = InstalledAppFlow.from_client_secrets_file(client_secret, scopes)
        creds = flow.run_local_server(port=0)
    else:
        raise ValueError(f'No valid `client_secret` at {client_secret}')
    print('pygdrive: Authentification succesful with a user account.')
    return creds


def _service_account_auth(service_account_secret, scopes) -> DriveClient:
    """ authenticates pygrive with a service account """
    if service_account_secret in os.environ:
        creds = service_account.Credentials.from_service_account_info(
            info = os.environ.get(service_account_secret),
            scopes = scopes
        )
    elif os.path.exists(service_account_secret):
        creds = service_account.Credentials.from_service_account_file(
            filename = service_account_secret,
            scopes = scopes
        )
    else:
        raise ValueError('No valid service_account_secret.')

    return DriveClient(creds=creds)
