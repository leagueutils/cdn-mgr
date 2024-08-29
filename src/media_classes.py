from __future__ import annotations

import abc
import hashlib
import os
import re

import cv2
import numpy as np

from leagueutils.errors import CDNException

IMAGE_TYPES = ['png', 'jpg', 'jpeg']
FONT_TYPES = ['otf', 'ttf']
NAME_PAT = re.compile(r'\d+-\w+/\w+\.[a-z]+')

MAX_FILE_SIZE_BYTES = 1234567  # todo: changeme


class MediaClass(abc.ABC):
    media_class: str = ''

    def __init__(self):
        self.ttl = None

    @classmethod
    def from_class_name(cls, media_class: str) -> MediaClass:
        match media_class:
            case 'team-logo':
                _cls = TeamLogo
            case 'clan-badge':
                _cls = ClanBadge
            case 'tournament-logo':
                _cls = TournamentLogo
            case 'league-logo':
                _cls = LeagueLogo
            case 'creator-logo':
                _cls = CreatorLogo
            case 'font':
                _cls = Font
            case _:
                raise CDNException('Invalid media type')
        return _cls()

    def get_storage_path(self, base_path: str, media_id: str, extension: str):
        return os.path.join(f'{base_path}', self.media_class, f'{media_id}.{extension}')

    def get_symlink_path(self, base_path: str, name: str, extension: str):
        return os.path.join(f'{base_path}', self.media_class.split('-')[0] + 's', f'{name}.{extension}')

    @abc.abstractmethod
    def validate(self, media_bytes: bytes, filename: str):
        pass

    @abc.abstractmethod
    def hash(self, media_bytes: bytes):
        pass


class Image(MediaClass):
    media_class = 'image'

    def hash(self, media_bytes: bytes):
        bytes_as_np_array = np.frombuffer(media_bytes, dtype=np.uint8)
        im = cv2.imdecode(bytes_as_np_array, cv2.IMREAD_GRAYSCALE)
        hsh = cv2.img_hash.BlockMeanHash.create()
        return hsh.compute(im)

    def validate(self, media_bytes: bytes, filename: str):
        if not NAME_PAT.match(filename):
            raise CDNException('Invalid name')

        if filename.split('.')[-1] not in IMAGE_TYPES:  # todo: check based on file magic?
            raise CDNException('Invalid file type')

        if media_bytes and len(media_bytes) > MAX_FILE_SIZE_BYTES:
            raise CDNException('File too large')


class Font(MediaClass):
    media_class = 'font'

    def hash(self, media_bytes: bytes):
        return hashlib.sha256(media_bytes, usedforsecurity=False)

    def validate(self, media_bytes: bytes, filename: str):
        if not NAME_PAT.match(filename):
            raise CDNException('Invalid name')

        if filename.split('.')[-1] not in FONT_TYPES:
            raise CDNException('Invalid file type')

        if media_bytes and len(media_bytes) > MAX_FILE_SIZE_BYTES:
            raise CDNException('File too large')


class TeamLogo(Image):
    media_class = 'team-logo'

    def __init__(self):
        super().__init__()
        self.ttl = 15778800  # half a year, in seconds


class ClanBadge(Image):
    media_class = 'clan-badge'


class TournamentLogo(Image):
    media_class = 'tournament-logo'


class LeagueLogo(Image):
    media_class = 'league-logo'


class CreatorLogo(Image):
    media_class = 'creator-logo'
