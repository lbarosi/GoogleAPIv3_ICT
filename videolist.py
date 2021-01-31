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
#--------------------------------------
#----Massage ICT/UFCG data specific functions
def do_list():
    """Reads the form list and organize the information, validating the existence of the projects.

    Args:
        path (str): describe where the sheet is `path`.

    Returns:
        type: DataFrame with DATA.

    """
    # Awful but I do not have patience to proper arguments now
    colunas = ['ID', 'Título do Projeto', 'Docente', 'Centro', 'Unidade',
               'Área Conhecimento', 'Aluno', 'CPF Aluno', 'Cota Bolsa','TIPO']
    # Employees
    servidores = pd.read_excel('./DATA/UFCG_Servidores_Ativos.xls', converters={'CPF':str})
    servidores = servidores[['CPF','Nome']]
    # Data from google form
    formularios = pd.read_csv('./DATA/Formulário_ICT_VIDEOS.csv', converters={'CPF_ALUNO':str, 'CPF_ORIENTADOR':str})
    formularios = formularios.dropna(axis=1, how='any')
    formularios['CPF_ORIENTADOR'] = formularios['CPF_ORIENTADOR'].apply(
        lambda row: re.sub(r"\D", "", row))
    formularios['CPF_ALUNO'] = formularios['CPF_ALUNO'].apply(
        lambda row: re.sub(r"\D", "", row))
    formularios['TIMESTAMP'] = pd.to_datetime(formularios['TIMESTAMP'])
    # read projects from lists SAAP. We do not have consolidated sheets.
    PIBIC = pd.read_excel('./DATA/PIBIC-2019.xls', converters={'CPF Aluno':str})
    PIVIC = pd.read_excel('./DATA/PIVIC-2019.xls', converters={'CPF Aluno':str})
    PIVIC_1 = pd.read_excel('./DATA/PIVIC-2019-1.xls', converters={'CPF Aluno':str})
    PIBITI = pd.read_excel('./DATA/PIBITI-2019.xls', converters={'CPF Aluno':str})
    PIVITI = pd.read_excel('./DATA/PIVITI-2019.xls', converters={'CPF Aluno':str})
    PIBIC['TIPO'] = 'PIBIC'
    PIVIC['TIPO'] = 'PIVIC'
    PIVIC_1['TIPO'] = 'PIVIC'
    PIBITI['TIPO'] = 'PIBITI'
    PIVITI['TIPO'] = 'PIVITI'
    projetos = pd.concat([PIBIC,PIVIC,PIVIC_1, PIBITI, PIVITI])
    # massage
    projetos = projetos[colunas]
    projetos = projetos.rename(columns={'Título do Projeto':'TITULO',
                                        'Docente':'DOCENTE',
                                        'Centro':'CENTRO',
                                        'Unidade':'UA',
                                        'Área Conhecimento':'AREA',
                                        'Aluno':'ALUNO',
                                        'CPF Aluno':'CPF_ALUNO',
                                        'Cota Bolsa':'BOLSA'})
    projetos.CPF_ALUNO = projetos.CPF_ALUNO.astype(str)
    projetos['DOCENTE'] = projetos['DOCENTE'].apply(
        lambda row: unidecode.unidecode(row))
    # Join research information
    dados_projetos = pd.merge(
        left=projetos, right=servidores,
        left_on='DOCENTE', right_on='Nome').drop('Nome',1)
    # check students
    dados_videos = pd.merge(
        left=dados_projetos, right=formularios,
        left_on='CPF_ALUNO', right_on='CPF_ALUNO')
    videos = dados_videos[
        dados_videos['CPF_ORIENTADOR'] == dados_videos['CPF']
    ]
    #eliminating duplicates and picking the most recent one
    videos_validos = videos.sort_values('TIMESTAMP').drop_duplicates('CPF_ALUNO',keep='last')
    #prepare the name in youtube
    videos_validos['LINK_VIDEO'] = videos_validos['LINK_VIDEO'].apply(lambda row: row.split('=')[-1])
    videos_validos['title'] = videos_validos.apply(lambda row:
                         'ICT-2020-' + '-'+ row['TIPO'] + '-'+row['AREA'] + '-' + '-' + row['CENTRO'] +
                         '-' + row['UA'] + ':  ' +
                         str(row['TITULO'])[0 : min(len(str(row['TITULO'])),30)] + '...',
                         axis = 1
                        )
    videos_validos['description'] = 'Videos para avaliação dos projetos de Iniciação Científica e Tecnológica, vigência 2019 - 2020, da Universidade Federal de Campina Grande. Provisoriamente armazenados nesta canal por problemas técnicos.'
    # Category: Education
    videos_validos['category'] = '27'
    videos_validos['keywords'] = videos_validos.apply(lambda row:
                         'UFCG,PRPG,PIBIC,PIBITI,' + row['AREA'] +',' + row['CENTRO'],
                         axis = 1
                        )
    return videos_validos

def do_subset(listadf, tipo='UA'):
    """Pick raw data and organize in accord to specified key

    Args:
        listadf (type): dataframe from do_list `listadf`.
        tipo (type): Description type of selection for playlists `tipo`. Defaults to 'UA'.

    Returns:
        type: DataFrame filtered

    """
    videos_validos = listadf
    listas = ['CENTRO','UA','AREA']
    categorias = [videos_validos[el].unique().tolist() for el in listas]
    playlists = [ videos_validos[ videos_validos[el] == categ ]['ID']
        for el in listas for categ in categorias[listas.index(el)] ]
    column_names = ['TIPO', 'CRITERIO', 'DADOS']
    df = pd.DataFrame(columns = column_names)
    POS = 0
    for item in listas:
        for item2 in categorias[listas.index(item)]:
            df.loc[len(df)] = [item, item2, videos_validos[videos_validos.index.isin(playlists[POS].index)]]
            POS += 1
    subdf = df[df['TIPO']==tipo]
    return  subdf
#--------------------------------------
def youtube_dict(df, args):
    if bool(args):
        df = df[df['CRITERIO']==args.criteria]
    dict_list = df.apply(lambda row: dict_struc(title = row['title'],
                                                category = row['category'],
                                                description = row['description'],
                                                keywords = row['keywords']), axis =1)
    df_out = pd.DataFrame(columns = ['ID','BODY'])
    df_out['ID'] = df['ID'].apply(lambda row: './VIDEO/' + str(row) + '.mp4')
    df_out['BODY']=dict_list
    return df_out

def youtube_upload_files(df,args):
    files = glob('./VIDEO/*.mp4')
    keys = []
    for file in files:
        ID = file.split('.')[0]
        dados = df[df['ID'==ID]]
        params = Namespace(title=dados['title'].iloc[0],
                            description=dados['description'].iloc[0],
                            category=dados['category'].iloc[0],
                            keywords=dados['keywords'].iloc[0],
                            secret = args.secret
                            )
        keys.append(youtube.youtube_upload(body, params, file))
    video_list = pd.DataFrame(keys, columns=['filename','video_id'])
    return video_list

def populate_playlists(service, videos_validos):
    try:
        videos = pd.read_csv('./videolist.csv')
        listas = pd.read_csv('./playlists.csv')
    except FileNotFoundError:
        exit("file {} does not exist".format(fname))
    videos['filename'] = videos['filename'].apply(lambda row: row.split('.')[0])
    listas['listname'] = lista['filename'].apply(lambda row: row.split('-')[-1])
    df = pd.merge(  left=videos_validos,
                    right=videos,
                    left_on='ID',
                    right_on='filename',
                    how='left'
                    )
    df = pd.merge(  left=df,
                    right=listas,
                    left_on='UA',
                    right_on='listname',
                    how='left'
                    )
    df = df[['video_id', 'list_id']]

    sleep_time = 60
    keys = []
    for lista in df['list_id']:
            for file in df[df['list_id']==lista]['video_id']:
                sleep_seconds = random.random() * sleep_time
                youtube.create_video_list(service, lista, file)
                time.sleep(sleep_seconds)
    print('Done populating playlists')
    return
#--------------------------------------
#----Main module to run in CLI
def parse_args(args):
    parser = argparse.ArgumentParser(description='Create Video Collection')
    #----arguments
    parser.add_argument('--secret', required=True, help='Json credentials for API')
    parser.add_argument('--operations',  required=True, help='Set of Operations to perform: all|download|upload|create_playlists|populate_playlists')
    parser.add_argument('--type', help ='UA|CENTRO|AREA', default='UA')
    parser.add_argument('--criteria', help='A particular subset', default='')
    parser.add_argument('-t', '--test', action='store_true', help="Test run")
    args = parser.parse_args()
    return args

def main(args):

    args = parse_args(args)
    secret = Namespace(secret=args.secret)
    videos_validos = do_list()
    videos_selected = do_subset(videos_validos, tipo = args.type)
    playlist_names = videos_validos.apply(lambda row:'UFCG-' + row['CENTRO']+'-'+row['UA'], axis = 1).unique().tolist()

    print('videolist initialization\n')

    if args.operations in ['create_playlists','all']:
        print('Creating Playlists')
        service = youtube.youtube_service(secret)
        playlists = youtube.create_all_playlists(service, lista=playlist_names)
        playlists.to_csv('./playlists.csv', sep=',', index=False)

    if args.operations in ['download','all']:
        print('Operation: Downloading Files')

        service = drive.gdrive_service(secret)
        df = videos_selected[videos_selected['TIPO']==args.type]
        if args.criteria:
            print('Selecting criteria ' + args.criteria)
            df = df[df['CRITERIO']==args.criteria].iloc[0,2]
            print('Preparing to download ' + str(df.shape[0]) + ' files')
            drive.download_lista(df, secret)
        else:
            for CRITERIO in df['CRITERIO'].unique():
                df1 = df[df['CRITERIO']==CRITERIO].iloc[0,2]
                drive.download_lista(df1, secret)

    if args.operations in ['upload','all']:
        print('Uploading Files')
        videos = youtube_upload_files(videos_validos, args)
        videos.to_csv('./videolist.csv', sep=',', index=False)

    if args.operations in ['populate_playlists','all']:
        service = youtube.youtube_service(secret)
        print('Populating playlists')
        populate_playlists(service, videos_validos)
    return None
#--------------------------------------
if __name__ == '__main__':
    import sys
    main(sys.argv)
