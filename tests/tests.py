#!/usr/bin/env python
"""
    This script read a LOCAL google form with video informations for R&D initiation projets for evaluation in 2021 due to sars-cov-2 pandemics. It generates leveral playlists, download files localli then upload them to youtube channel, creating proper tags.
    Author: Luciano Barosi
    Company: Universidade Federal de Campina Grande
    Created: 31/jan/2020
"""
#--------------------------------------
#----IMPORTS
import os
import sys
import time
import io
from glob import glob
import random
import numpy as np
import pandas as pd
import unidecode
import re
import argparse
from argparse import Namespace
#--------------------------------------
#---- Local Imports
import drive
import youtube
import videolist

try:
    videos = pd.read_csv('./videos.csv')
    listas = pd.read_csv('./playlists.csv')
except FileNotFoundError:
    exit("file {} does not exist".format(fname))
videos = videos[videos['video_title'].str.match('[0-9]{4}')]
listas['listname'] = listas['playlist_title'].apply(lambda row: row.split('-')[-1])
videos_validos['ID'] = videos_validos['ID'].astype(str)
df = pd.merge(  left=videos_validos,
                right=videos,
                left_on='ID',
                right_on='video_title',
                how='outer'
                )

df.shape

df = pd.merge(  left=df,
                right=listas,
                left_on='UA',
                right_on='listname',
                how='outer'
                )

df.shape
df
df.dropna().shape
df = df.sort_values(by=['ID'])
listID = df['ID'].unique()
n = 0
for ID in listID:
    n = n+1
    print('Updating {0} de {1}'.format(n,len(listID)))
    dados = df[df['ID']==ID]
    params = Namespace(title=dados['title'].iloc[0],
                        description=dados['description'].iloc[0],
                        category=dados['category'].iloc[0],
                        keywords=dados['keywords'].iloc[0]
                        )
    if params.keywords:
        tags = params.keywords.split(",")

    video_id = dados['video_id'].iloc[0]
    body = {
         "id": video_id,
         'snippet': {
              'title': params.title,
              "description": params.description,
              'tags': tags,
              'categoryId': params.category
         },
         "status": {
              "privacyStatus": 'public',
         },
    }
    print(body)
    time.sleep(20)
    response = youtube.update_video(service, body)
    print(response['id'])
