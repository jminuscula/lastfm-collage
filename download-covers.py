
import sys
import argparse
import os
import os.path
import json

import re
import asyncio
import aiohttp
import urllib.parse
import difflib


BASE_URL = "https://sticky-summer-lb.inkstone-clients.net/api/v1/search?term={q}&country=us&media=music&entity=album&genreId=&limit=10&lang=en_us"
MAX_CONCURRENT_REQUESTS = 25
MAX_CONCURRENT_DOWNLOADS = 25


def parse_args(args):
    parser = argparse.ArgumentParser(
        description='Download cover images for a list of music albums'
    )

    parser.add_argument(
        'albums_file', metavar='FILE',
        help='file containing artist-album search strings'
    )

    parser.add_argument(
        '-o', '--out',
        default='covers', dest='outdir',
        help='covers output directory (default: ./covers)'
    )

    return parser.parse_args(args)


def get(url, semaphore):
    with (yield from semaphore):
        response = yield from aiohttp.request('GET', url)
        return (yield from response.read())


def find_and_download_cover(query, outdir, req_semaphore, download_semaphore):
    url = BASE_URL.format(q=urllib.parse.quote(query))
    data_response = yield from get(url, req_semaphore)
    data = json.loads(data_response.decode())

    if not data.get('results', []):
        return

    album_query_scores = []
    for idx, album in enumerate(data['results']):
        try:
            album_query = "{} {}".format(album['artistName'], album['name'])
        except KeyError:
            continue
        query_score = difflib.SequenceMatcher(None, query, album_query).ratio()
        album_query_scores.append((query_score, album))
        if query_score == 1.0:
            break

    score, album_info = max(album_query_scores, key=lambda s_a: s_a[0], default=(0, None))
    if score  < 0.5:
        print('[NOT FOUND] {}'.format(query))
        return None

    width, height = album_info['artwork']['width'], album_info['artwork']['height']
    cover_url = album_info['artwork']['url'].format(w=width, h=height, f='png')

    cover = yield from get(cover_url, download_semaphore)
    filename = "{} - {}.png".format(album_info['artistName'], album_info['name'])
    filename = re.sub(r'[\/*?;:]', '_', filename)
    outfile = os.path.join(outdir, filename)
    with open(outfile, 'wb') as cover_file:
        cover_file.write(cover)

    return True


def download_covers(albums_file, outdir):
    if not os.path.exists(albums_file):
        print('albums file not found')
        sys.exit(1)

    if not os.path.exists(outdir):
        os.mkdir(outdir)

    elif not os.path.isdir(outdir):
        print('{} is not a directory'.format(outdir))
        sys.exit(1)

    tasks = []
    req_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
    with open(albums_file) as queries:
        for query in queries.readlines():
            task = find_and_download_cover(query.strip(), outdir, req_semaphore, download_semaphore)
            tasks.append(asyncio.Task(task))

    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait(tasks))
    loop.close()


if __name__ == '__main__':
    args = parse_args(sys.argv[1:])
    download_covers(args.albums_file, args.outdir)
