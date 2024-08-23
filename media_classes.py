import abc
import hashlib
import os
import re

import cv2
import numpy as np

from leagueutils.errors import CDNError

IMAGE_TYPES = ['png', 'jpg', 'jpeg']
FONT_TYPES = ['otf', 'ttf']
NAME_PAT = re.compile(r'\d+-\w+/\w+\.[a-z]+')

MAX_FILE_SIZE_BYTES = 1234567  # todo: changeme


class MediaClass(abc.ABC):
    def __init__(self, filename: str, media_bytes: bytes | None = None):
        self.bytes = media_bytes
        self.name = filename
        self.ttl = None
        self.__extension = self.validate()

    @classmethod
    def from_class_name(cls, media_class: str, filename: str, media_bytes: bytes | None = None):
        match media_class:
            case 'team-logo':
                _cls = TeamLogo
            case 'clan-badge':
                _cls = ClanBadge
            case 'tournament-logo':
                _cls = TournamentLogo
            case 'league-logo':
                _cls = LeagueLogo
            case 'streamer-logo':
                _cls = CreatorLogo
            case 'font':
                _cls = Font
            case _:
                raise CDNError('Invalid media type')
        return _cls(filename, media_bytes)

    @property
    def media_class(self):
        class_name = self.__class__.__name__
        output = class_name[0].lower()
        for char in class_name[1:]:
            if char.isupper():
                output += '-' + char.lower()
            else:
                output += char
        return output

    @property
    def storage_path_template(self):
        return os.path.join('{base_path}', self.media_class, '{media_id}.' + self.__extension)

    @abc.abstractmethod
    def validate(self):
        pass

    @abc.abstractmethod
    def hash(self):
        pass


class Image(MediaClass):
    def hash(self):
        bytes_as_np_array = np.frombuffer(self.bytes, dtype=np.uint8)
        im = cv2.imdecode(bytes_as_np_array, cv2.IMREAD_GRAYSCALE)
        hsh = cv2.img_hash.BlockMeanHash.create()
        return hsh.compute(im)

    def validate(self):
        if not NAME_PAT.match(self.name):
            raise CDNError('Invalid name')

        if (extension := self.name.split('.')[-1]) not in IMAGE_TYPES:
            raise CDNError('Invalid file type')

        if self.bytes and len(self.bytes) > MAX_FILE_SIZE_BYTES:
            raise CDNError('File too large')

        return extension


class Font(MediaClass):
    def hash(self):
        return hashlib.sha256(self.bytes, usedforsecurity=False)

    def validate(self):
        if not NAME_PAT.match(self.name):
            raise CDNError('Invalid name')

        if (extension := self.name.split('.')[-1]) not in FONT_TYPES:
            raise CDNError('Invalid file type')

        if self.bytes and len(self.bytes) > MAX_FILE_SIZE_BYTES:
            raise CDNError('File too large')

        return extension


class TeamLogo(Image):
    def __init__(self, filename: str, media_bytes: bytes | None = None):
        super().__init__(filename, media_bytes)
        self.ttl = 15778800  # half a year, in seconds


class ClanBadge(Image):
    pass


class TournamentLogo(Image):
    pass


class LeagueLogo(Image):
    pass


class CreatorLogo(Image):
    pass
