import argparse
import logging
import os
import taglib
import json
import re
import warnings
from tqdm import tqdm
from eyed3.plugins.art import ArtFile
from logging import info, warning, error, debug
from pathlib import Path

'''HACK: I really don\'t care about possible nested sets. Regex is complicated enough without having to deal with writing compliant and clear expressions.'''
warnings.filterwarnings('ignore', category=FutureWarning)


logging.basicConfig(
    level=logging.INFO,
    format='(%(asctime)s) [%(name)s:%(levelname)s] [%(module)s:%(lineno)d] %(message)s',
    datefmt='%m/%d/%Y %I:%M:%S %p',
    handlers=[
        logging.FileHandler('musiclibcleaner.log', 'w', encoding='utf-8'),
        logging.StreamHandler()
    ],
    encoding='utf-8'
)

ap = argparse.ArgumentParser()
ap.add_argument('-p', '--path', type=str, required=True, help='Library path')
ap.add_argument('-o', '--output-path', type=str, required=True, help='Report output path')
ap.add_argument('-r', '--refresh', action=argparse.BooleanOptionalAction, help='Force refresh')
ap.add_argument('-sa', '--skip-album-covers', action=argparse.BooleanOptionalAction, help='Skip album cover scan')

args = vars(ap.parse_args())


def create_paths(library_path, output_path):
    if not os.path.exists(library_path):
        error(f'Library at "{library_path}" does not exist. Exiting.')
        exit(1)

    if not os.path.exists(output_path):
        os.mkdir(output_path)


def scan_library(library_path):
    global args

    supported_formats = [ 'mp3', 'aac', 'm4a', 'ogg', 'alac', 'ape', 'wav', 'MP3', 'AAC', 'M4A', 'OGG', 'ALAC', 'APE', 'WAV' ]

    media_files = []

    cache_path = os.path.join(library_path, 'files.json')
    if os.path.exists(cache_path) and not args.get('refresh', False):
        debug(f'Loading file list from cache in "{cache_path}"...')
        with open(cache_path, 'r', encoding='utf-8') as cf:
            media_files = cf.read().rstrip().split('\n')
    else:
        if os.path.exists(cache_path):
            os.remove(cache_path)

        info(f'Scanning for compatible media in "{library_path}", this will take a very long time...')
        for file_format in supported_formats:
            media_files.extend([ str(path) for path in Path(os.path.join(library_path)).rglob(f'*.{file_format}') ])

        if len(media_files):
            debug(f'Storing the result in "{cache_path}"...')
            with open(cache_path, 'w', encoding='utf-8') as cf:
                cf.write('\n'.join(media_files))
    
    info(f'Found {len(media_files)} files!')

    return media_files


def determine_erroneous_track_num(media_file_name, media_info_item):
    debug(f'Checking "{media_file_name}" for erroneous track number tag...')
    
    clean = 'TRACKNUMBER' in media_info_item['tags'] and isinstance(media_info_item['tags']['TRACKNUMBER'], str) and re.match('^[[1-9][0-9]{0,2}|100]|/[[[1-9][0-9]{0,2}|100]]$', media_info_item['tags']['TRACKNUMBER'])
    
    debug(f'"{media_file_name}" - TRACKNUMBER - {"PASSED" if clean else "FAILED"}')
    
    return not clean


def determine_erroneous_disc_num(media_file_name, media_info_item):
    debug(f'Checking "{media_file_name}" for erroneous disc number tag...')
    
    clean = 'DISCNUMBER' not in media_info_item['tags'] or (isinstance(media_info_item['tags']['DISCNUMBER'], str) and (re.match('^[[1-9][0-9]{0,2}|100]|/[[[1-9][0-9]{0,2}|100]]$', media_info_item['tags']['DISCNUMBER']) or media_info_item['tags']['DISCNUMBER'] == ''))
    
    debug(f'"{media_file_name}" - DISCNUMBER - {"PASSED" if clean else "FAILED"}')
    
    return not clean


def determine_erroneous_date(media_file_name, media_info_item):
    debug(f'Checking "{media_file_name}" for date tag...')
    
    clean = 'DATE' in media_info_item['tags'] and isinstance(media_info_item['tags']['DATE'], str) and re.match('^[0-9][0-9][0-9][0-9]$', media_info_item['tags']['DATE'])
    
    debug(f'"{media_file_name}" - DATE - {"PASSED" if clean else "FAILED"}')
    
    return not clean


def scan_media_info(library_path, media_files):
    global args
    media_info = {}

    cache_path = os.path.join(library_path, 'info.json')
    if os.path.exists(cache_path) and not args.get('refresh', False):
        info(f'Loading media info from cache in "{cache_path}"...')
        with open(cache_path, 'r', encoding='utf-8') as cf:
            media_info = json.loads(cf.read())
    else:
        if os.path.exists(cache_path):
            os.remove(cache_path)

        info(f'Scanning for media info in "{library_path}", grab a coffee...')
        index = 0
        for media_file in tqdm(media_files):
            index += 1
            debug(f'({index} / {len(media_files)}) Scanning for media info in "{media_file}"...')
            try:
                with taglib.File(media_file, save_on_exit=False) as file_info:
                    if not file_info:
                        warning(f'Warning: Failed to scan "{media_file}"!')
                        media_info[media_file] = {
                            'tags': {},
                            'errored': True,
                            'erroneous_tags': [],
                            'has_cover': False
                        }
                    else:
                        media_info_item = {
                            'tags': {
                                'ARTIST': ','.join(file_info.tags['ARTIST']) if 'ARTIST' in file_info.tags else None,
                                'ALBUMARTIST': ','.join(file_info.tags['ALBUMARTIST']) if 'ALBUMARTIST' in file_info.tags else None,
                                'ALBUM': file_info.tags['ALBUM'][0] if 'ALBUM' in file_info.tags else None,
                                'TITLE': file_info.tags['TITLE'][0] if 'TITLE' in file_info.tags else None,
                                'TRACKNUMBER': file_info.tags['TRACKNUMBER'][0] if 'TRACKNUMBER' in file_info.tags else None,
                                'DISCNUMBER': file_info.tags['DISCNUMBER'][0] if 'DISCNUMBER' in file_info.tags else None,
                                'DATE': file_info.tags['DATE'][0] if 'DATE' in file_info.tags else None
                            },
                            'errored': False,
                            'erroneous_tags': [],
                            'has_cover': False
                        }

                        debug(f'Found tags for "{media_file}": {json.dumps(media_info_item["tags"])}')
                    
                    media_info[media_file] = media_info_item
            except:
                warning(f'Warning: Failed to scan "{media_file}"!')
                media_info[media_file] = {
                    'tags': {},
                    'has_cover': False,
                    'errored': True,
                    'erroneous_tags': [],
                    'has_cover': False
                }
            
        if len(media_info):
            info(f'Finished scanning for media info in "{library_path}"!')
            with open(cache_path, 'w', encoding='utf-8') as cf:
                cf.write(json.dumps(media_info))
    
    info(f'Found {len(media_info)} media info entries!')

    return media_info


def scan_album_covers(media_files, media_info):
    info('Checking for front album cover...')
    for media_file in tqdm(media_files):
        media_info_item = media_info[media_file]
        try:
            art_file = ArtFile(media_file)
            if not art_file.image_data and not art_file.mime_type:
                debug(f'"{media_info} has no front cover data')
                media_info_item['has_cover'] = False
            else:
                debug(f'"{media_info} has cover data with MIME type {art_file.mime_type}')
                media_info_item['has_cover'] = True
        except:
            warning(f'Warning: Failed to check for the front album cover for "{media_file}"!')
            media_info_item['has_cover'] = False

    return media_info


def scan_erroneous_tags(media_files, media_info):
    info('Checking for erroneous tags...')
    for media_file in tqdm(media_files):
        media_info_item = media_info[media_file]
        if determine_erroneous_track_num(media_file, media_info_item) and 'TRACKNUMBER' not in media_info_item['erroneous_tags']:
            media_info_item['erroneous_tags'].append('TRACKNUMBER')
        if determine_erroneous_disc_num(media_file, media_info_item) and 'DISCNUMBER' not in media_info_item['erroneous_tags']:
            media_info_item['erroneous_tags'].append('DISCNUMBER')
        if determine_erroneous_date(media_file, media_info_item) and 'DATE' not in media_info_item['erroneous_tags']:
            media_info_item['erroneous_tags'].append('DATE')

    return media_info


def dict_list_to_html(dict_list):
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Report</title>
        <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
    </head>
    <body>
        <div class="container">
            <table class="table table-bordered">
                <thead class="thead-dark">
                    <tr>"""
    
    for key in dict_list[0].keys():
        html += f"<th>{key}</th>"
    html += "</tr></thead><tbody>"
    
    for item in dict_list:
        html += "<tr>"
        for value in item.values():
            if isinstance(value, dict):
                inner_html = ""
                for inner_key, inner_value in value.items():
                    inner_html += f"<li>{inner_key}: {inner_value}</li>"
                html += f"<td><ul>{inner_html}</ul></td>"
            else:
                html += f"<td>{value}</td>"
        html += "</tr>"
    
    html += """
                </tbody>
            </table>
        </div>
    </body>
    </html>"""
    return html


library_path = args.get('path')
output_path = args.get('output_path')

create_paths(library_path, output_path)
media_files = scan_library(library_path)
media_info = scan_erroneous_tags(media_files, scan_media_info(library_path, media_files))
if not args.get('skip_album_covers', False):
    media_info = scan_album_covers(media_files, media_info)

if len(media_info):
    info(f'Saving a report to "{output_path}"...')
    html = dict_list_to_html([ media_info[key] for key in media_info if len(media_info[key]['erroneous_tags']) or (not media_info[key]['has_cover'] and not args.get('skip_album_covers')) or media_info[key]['errored'] ])
    with open(os.path.join(output_path, 'report.html'), 'w', encoding='utf-8') as hf:
        hf.write(html)
    
    with open(os.path.join(output_path, 'report.json'), 'w', encoding='utf-8') as jf:
        jf.write(json.dumps(media_info))
