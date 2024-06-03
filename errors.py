from leagueutils.errors import LUBaseException


class CDNError(LUBaseException):
    pass


class MediaNotFound(CDNError):
    def __init__(self, message=''):
        self.code = 404
        self.message = message
