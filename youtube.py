#!/usr/bin/python
"""manage uploads and playlists in youtube"""

#----IMPORTS
import os
import sys
import time
import io
from glob import glob
sys.path.insert(0, './DATA/')
import random
import numpy as np
import pandas as pd
import unidecode
import re
import argparse
import httplib2
from apiclient.discovery import build
from apiclient.errors import HttpError
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow
from oauth2client import tools
from apiclient.http import MediaFileUpload
from apiclient.http import MediaIoBaseDownload
from tenacity import retry, retry_if_exception_type, wait_exponential, stop_after_attempt
#--------------------------------------
# Explicitly tell the underlying HTTP transport library not to retry, since
# we are handling retry logic ourselves.
httplib2.RETRIES = 1
MAX_RETRIES = 10
# Always retry when these exceptions are raised.
RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError)
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
VALID_PRIVACY_STATUSES = ("public", "private", "unlisted")
#----Google API credentials
def open_credentials(SCOPE, CLIENT_SECRETS_FILE):
    """Create google credentials for the services of the module

    Args:
        SCOPE (str or list): Check the scopes in youtube API `SCOPE`.
        CLIENT_SECRETS_FILE (str): file where credentials are stored `CLIENT_SECRETS_FILE`.

    Returns:
        type: credential flow object.

    """

    MISSING_CLIENT_SECRETS_MESSAGE = """
    WARNING: Please configure OAuth 2.0

    To make this sample run you will need to populate the client_secrets.json file
    found at:

       %s

    with information from the API Console
    https://console.developers.google.com/

    For more information about the client_secrets.json file format, please visit:
    https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
    """
    flow = flow_from_clientsecrets(CLIENT_SECRETS_FILE,
      message=MISSING_CLIENT_SECRETS_MESSAGE,
      scope=SCOPE)
    storage = Storage('./secret/{}-oauth2.json'.format(str(sys.argv[0])))
    credentials = storage.get()
    # You may pick the credentials from the browser
    if credentials is None or credentials.invalid:
        flags = tools.argparser.parse_args(args=[])
        credentials = run_flow(flow, storage, flags)

    return credentials

def youtube_service(args):
    """Instantiate a youtube service.

    Args:
        secret (str): json credential file `args`.

    Returns:
        type: youtube service

    """

    CLIENT_SECRETS_FILE = args.secret
    SCOPE = 'https://www.googleapis.com/auth/youtube'
    try:
        CLIENT_SECRETS_FILE = args.secret
    except KeyError as e:
        CLIENT_SECRETS_FILE = './credentials.json'
        pass
    except NameError as e:
        CLIENT_SECRETS_FILE = './credentials.json'
        pass
    YOUTUBE_API_SERVICE_NAME = "youtube"
    YOUTUBE_API_VERSION = "v3"
    #----------------------------------
    credentials = open_credentials(SCOPE, CLIENT_SECRETS_FILE)
    #----------------------------------
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, http=credentials.authorize(httplib2.Http()))

    return youtube

def create_video_list(service, list_name=''):
    """Create a playlist in the authorized channel.

    Args:
        service (type): youtube service `service`.
        list_name (type): name of the playlist `list_name`. Defaults to ''.

    Returns:
        type: playlist ID.

    """
    playlists_insert_response = service.playlists().insert(
      part="snippet,status",
      body=dict(
        snippet=dict(
          title=list_name,
          description="Videos do Centro e Unidade Acadêmica referenciados"
        ),
        status=dict(
          privacyStatus="public"
        )
      )
    ).execute()
    print("New playlist id: %s" % playlists_insert_response["id"])
    return [list_name, playlists_insert_response["id"]]

# def create_all_playlists(service, lista = []):
#     """Create a list of playlist in the authorized channel. Process each name in 60s interval to avoid 503 ERROR.
#
#     Args:
#         service (type): youtube service `service`.
#         lista (type): list with the playlist names `lista`. Defaults to [].
#
#     Returns:
#         type: None
#
#     """
#
#     sleep_time = 60
#     keys = []
#     for item in lista:
#         sleep_seconds = random.random() * sleep_time
#         print( "Sleeping %f seconds and then retrying..." % sleep_seconds)
#         keys.append(response = create_video_list(service, list_name=item))
#         time.sleep(sleep_seconds)
#     print('Done creating playlists')
#     playlists = pd.DataFrame(keys, columns=['listname','list_id'])
#     return playlists

#--------------------------------------
def insert_video_playlist(service, playlist, video):
    """Insert video in playlist of authorized channel. playlistID and videoID are needed

    Args:
        service (type): Description of parameter `service`.
        playlist (type): Description of parameter `playlist`.
        video (type): Description of parameter `video`.

    Returns:
        type: Description of returned object.

    """
    playlists_insert_video = service.playlistsitems().insert(part="snippet",
        body=dict(snippet=dict(
            playlistId=playlist,
            resourceId={
                kind="youtube#video",
                videoId=video
                }
            )
        )
    ).execute()

    return None

#--------------------------------------

def initialize_upload(service, filename, body):
    """Initiate connection to upload and pass to connection manager .

    Args:
        service (type): youtube `service`.
        filename (type): path to filename to be uploaded `filename`.
        body (type): structured block of dict.struct() with the parameters for the video on youtube `body`.
        args (type): Description of parameter `args`.

    Returns:
        type: None.

    """
    # Call the API's videos.insert method to create and upload the video.
    insert_request = service.videos().insert(
    part=",".join(body.keys()),
    body=body,
    media_body=MediaFileUpload(filename, chunksize=-1, resumable=True)
    )
    video_id = manage_upload(insert_request)
    return [filename, video_id]

def manage_upload(insert_request):
    """Manage exponential backoff for http retries.

    Args:
        insert_request (type): youtube service Media insert `insert_request`.

    Returns:
        type: status, response for the service

    """
    response = None
    error = None
    retry = 0

    while response is None:
        try:
            print( "Uploading file...")
            status, response = insert_request.next_chunk()
            if response is not None:
                if 'id' in response:
                    print("{}% uploaded".format(response['id']))
                else:
                    exit("The upload failed with an unexpected response: %s" % response)
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = "A retriable HTTP error %d occurred:\n%s" % (e.resp.status, e.content)
            else:
                raise
        except RETRIABLE_EXCEPTIONS as e:
            error = "A retriable error occurred: %s" % e

        if error is not None:
            print( error)
            retry += 1
            if retry > MAX_RETRIES:
                exit("No longer attempting to retry.")
            max_sleep = 2 ** retry
            sleep_seconds = random.random() * max_sleep
            print( "Sleeping %f seconds and then retrying..." % sleep_seconds)
            time.sleep(sleep_seconds)
    return response['id']

def youtube_upload(body, args, filename):
    """Manage the upload process.

    Args:
        body (type): parameters for youtube dict_struct() `body`.
        args (type): CLI args should contain secrets (json file) `args`.
        filename (type): path to the file to be uploaded `filename`.

    Returns:
        type: Description of returned object.

    """
    if not os.path.exists(filename):
        exit("Please specify a valid file")
    youtube = youtube_service(args)
    try:
        video_keys = initialize_upload(youtube, filename, body)
    except HttpError as e:
        print( "An HTTP error %d occurred:\n%s" % (e.resp.status, e.content))
    return video_keys

def dict_struc(args):
    """Create block to insert youtube info.

    Args:
        keyword (type): Description of parameter `args`.
        title (type): Description of parameter `args`.
        description (type): Description of parameter `args`.
        category (type): Description of parameter `args`.

    Returns:
        type: body dictionary

    """
    tags = None
    if args.keywords:
        tags = args.keywords.split(",")

    body=dict(
    snippet=dict(
      title=args.title,
      description=args.description,
      tags=tags,
      categoryId=args.category),
    status=dict(privacyStatus=VALID_PRIVACY_STATUSES[0])
    )
    return body

#----Module as script
def parse_args(args):
    parser = argparse.ArgumentParser(description='Download from google drive')
    #----arguments
    parser.add_argument('--filename', required=True)
    parser.add_argument('--title', required=True)
    parser.add_argument('--description', required=True)
    parser.add_argument('--keywords')
    parser.add_argument('--category', default='22')
    parser.add_argument('--secret',  required=True, help='OAUTH2 credentials JSON')
    args = parser.parse_args()
    return args

def main(args):
    """Upload file to youtube.

    Args:
        keyword (type): Description of parameter `args`.
        title (type): Description of parameter `args`.
        description (type): Description of parameter `args`.
        category (type): Description of parameter `args`.
        secret (type): Description of parameter `args`.

    Returns:
        type: None.

    """
    print('Preparing Upload')
    args = parse_args(args)
    body = dict_struc(args)
    youtube_upload(body,args,args.filename )
    return None

if __name__ == '__main__':
    main(sys.argv)
