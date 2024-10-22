from __future__ import annotations

import abc
import hashlib
import os

import cv2
import filetype
import numpy as np

from leagueutils.errors import CDNException

IMAGE_TYPES = ['image/jpeg', 'image/png']
FONT_TYPES = ['application/font-sfnt']

MAX_FILE_SIZE_BYTES = 8 * 1024**2  # 8MB in Bytes


class MediaClass(abc.ABC):
    media_class: str = ''
    valid_types: list[str] = []

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
            case 'template':
                _cls = Template
            case 'font':
                _cls = Font
            case _:
                raise CDNException(code=400, message='Invalid media type')
        return _cls()

    @classmethod
    def get_storage_path(cls, base_path: str, media_id: str, extension: str = 'png'):
        return os.path.join(f'{base_path}', f'{media_id}.{extension}')

    @classmethod
    def get_symlink_path(cls, base_path: str, filename: str):
        return os.path.join(f'{base_path}', cls.media_class + 's', filename)

    @classmethod
    def validate(cls, media_bytes: bytes):
        if filetype.guess_mime(media_bytes) not in cls.valid_types:
            raise CDNException(code=400, message='Invalid file type')

        if len(media_bytes) > MAX_FILE_SIZE_BYTES:
            raise CDNException(code=400, message='File too large')

    @staticmethod
    @abc.abstractmethod
    def hash(media_bytes: bytes):
        pass


class Image(MediaClass):
    media_class = 'image'
    valid_types = IMAGE_TYPES

    @staticmethod
    def hash(media_bytes: bytes):
        bytes_as_np_array = np.frombuffer(media_bytes, dtype=np.uint8)
        im = cv2.imdecode(bytes_as_np_array, cv2.IMREAD_GRAYSCALE)
        hsh = cv2.img_hash.BlockMeanHash.create()
        return hsh.compute(im)


class Font(MediaClass):
    media_class = 'font'
    valid_types = FONT_TYPES

    @staticmethod
    def hash(media_bytes: bytes):
        return hashlib.sha256(media_bytes, usedforsecurity=False)


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


class Template(Image):
    media_class = 'template'
