#!/usr/bin/env python3.5

import sys
import os.path
import argparse

import re
import functools
import itertools

import json
import urllib.request


API_KEY = "44bc296a277832658f7bd8cba3b7e5ae"
TOP_ALBUMS_URL = "http://ws.audioscrobbler.com/2.0/?method=user.gettopalbums&user={user}&api_key={key}&limit={limit}&page={page}&format=json"
TOP_ALBUMS_REQ_LIMIT = 1000


def parse_args(args):

    parser = argparse.ArgumentParser(
        description="Create a top album list from last.fm scrobblings",
    )

    parser.add_argument(
        'user',
        metavar='USER', nargs='+',
        help='last.fm usernames to fetch scrobblings from'
    )

    parser.add_argument(
        '-n', '--number', type=int,
        metavar='NUMBER', dest='number', default=500,
        help='max number of albums to fetch (default: 500)',
    )

    parser.add_argument(
        '-a', '--alternate',
        action='store_true',
        help='force an equal number of albums from each user'
    )

    return parser.parse_args(args)


class Album:

    def __init__(self, album_data):
        self.artist = album_data['artist']['name']
        self.playcount = int(album_data['playcount'])
        self.title = self.clean_title(album_data['name'])

    def clean_title(self, title):
        re_translate = (
            (r'deluxe|collector\'s|remaster|advance|special|'
              'anniversary|edition|version|bonus|track', ''),
            (r'disc\s*\d+', ''),
            (r' & ', ' and '),
            (r'\(\s*\)|\[\s*\]', ''),
        )

        cleaned_title = title
        for regexp, trans in re_translate:
            regexp = re.compile(regexp, re.IGNORECASE)
            cleaned_title = regexp.sub(trans, cleaned_title)

        return cleaned_title.strip()

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __hash__(self):
        return hash((self.artist, self.title))


def get_user_albums(username, limit):
    albums = []
    req_page = 1
    req_limit = min(limit, TOP_ALBUMS_REQ_LIMIT)
    while len(albums) < limit:
        req_url = TOP_ALBUMS_URL.format(user=username, limit=req_limit, page=req_page, key=API_KEY)
        with urllib.request.urlopen(req_url) as req:
            data = json.loads(req.read().decode())
            data_albums = data.get('topalbums', {}).get('album')
            if not data_albums:
                break
            albums += list(map(Album, data_albums))
            req_page += 1
    return albums


def _remove_album_duplicates(user_albums):
    if len(user_albums) < 2:
        return user_albums

    unique = set()
    unique_user_albums = []
    for albums in user_albums:
        unique_user_album = set(albums).difference(unique)
        unique = unique.union(unique_user_album)
        unique_user_albums.append(sorted(unique_user_album, key=lambda a: -a.playcount))

    return unique_user_albums


def _get_alternate_top_albums(user_albums, limit):

    def roundrobin(*iterables):
        # https://docs.python.org/3.5/library/itertools.html#itertools-recipes
        pending = len(iterables)
        nexts = itertools.cycle(iter(it).__next__ for it in iterables)
        while pending:
            try:
                for next in nexts:
                    yield next()
            except StopIteration:
                pending -= 1
                nexts = itertools.cycle(itertools.islice(nexts, pending))

    user_albums = _remove_album_duplicates(user_albums)
    alternates = roundrobin(*user_albums)
    top_albums = itertools.islice(alternates, limit)
    return list(top_albums)


def _get_overall_top_albums(user_albums, limit):
    user_albums = _remove_album_duplicates(user_albums)
    unique_albums = functools.reduce(lambda a, b: a.union(set(b)), user_albums, set())
    unique_albums = sorted(unique_albums, key=lambda a: -a.playcount)
    return unique_albums[:limit]


def get_top_albums(usernames, limit, alternate, dup_factor=2):
    """
    Gets a `limit` number of albums from the scrobblings of each user in
    usernames. If `alternate` is False, the albums are fetched by popularity.
    Otherwise, an album from each user is fetched until `limit` is reached.
    """
    user_limit = limit
    get_top_albums_fn = _get_overall_top_albums
    if alternate:
        # exceed limit to account for possible duplications.
        user_limit = dup_factor * limit / len(usernames)
        get_top_albums_fn = _get_alternate_top_albums

    user_albums = [get_user_albums(user, user_limit) for user in usernames]
    return get_top_albums_fn(user_albums, limit)


def print_album_list(usernames, n_albums, alternate):
    albums = get_top_albums(usernames, n_albums, alternate)
    album_titles = sorted(['{} {}'.format(a.artist, a.title) for a in albums])

    for title in album_titles:
        print(title)


if __name__ == '__main__':
    args = parse_args(sys.argv[1:])
    print_album_list(args.user, args.number, args.alternate)
