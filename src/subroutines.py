import os

from media_classes import MediaClass

from leagueutils.compontens.db import DBService
from leagueutils.errors import CDNException, DbNotFoundException
from leagueutils.models.cdn import Config

config = Config()
db = DBService()


async def _remove_media(medium: MediaClass, symlink: str):
    """subroutine to clean up a medium by symlink"""
    try:
        os.unlink(symlink)
        [media_id] = await db.fetchrow('DELETE FROM cdn.links WHERE link=$1 RETURNING media_id', symlink)
    except (DbNotFoundException, FileNotFoundError) as e:  # no linked image
        raise CDNException('No such file') from e

    [other_links] = await db.fetchrow('SELECT COUNT(*) FROM cdn.links WHERE media_id=$1')
    if other_links == 0:
        os.unlink(medium.get_storage_path(config.base_path, media_id, symlink.split('.')[-1]))
        await db.execute('DELETE FROM cdn.media WHERE media_id=$1', media_id)
