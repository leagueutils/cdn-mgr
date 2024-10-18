import os
import uuid

import aiofiles
import filetype

from leagueutils.components.db import DBService
from leagueutils.errors import CDNException, DbNotFoundException
from leagueutils.models.cdn import Config

from .media_classes import MediaClass

config = Config()
db = DBService()


async def delete_media(media_class: MediaClass, symlink: str):
    """subroutine to clean up a medium by symlink"""

    try:
        os.unlink(symlink)
        [media_id] = await db.fetchrow('DELETE FROM cdn.links WHERE link=$1 RETURNING media_id', symlink)
    except (DbNotFoundException, FileNotFoundError) as e:  # no linked image
        raise CDNException(code=404, message='No such file') from e

    [other_links] = await db.fetchrow('SELECT COUNT(*) FROM cdn.links WHERE media_id=$1')
    if other_links == 0:
        os.unlink(media_class.get_storage_path(config.base_path, media_id, symlink.split('.')[-1]))
        await db.execute('DELETE FROM cdn.media WHERE media_id=$1', media_id)


async def store_media(media_class: MediaClass, media_bytes: bytes, filename: str | None = None) -> str:
    """subroutine to store a medium"""

    media_hash = media_class.hash(media_bytes)
    try:
        [media_id] = await db.fetchrow('SELECT media_id FROM cdn.media WHERE hash=$1', media_hash)
        store = False
    except DbNotFoundException:
        store = True
        media_id = str(uuid.uuid4())

    if filename is not None:
        extension = filename.split('.')[-1]
    else:
        extension = filetype.guess_extension(media_bytes)

    fp = media_class.get_storage_path(base_path=config.base_path, media_id=media_id, extension=extension)
    if store:
        async with aiofiles.open(fp, 'wb+') as outfile:
            await outfile.write(media_bytes)
        await db.execute('INSERT INTO cdn.media VALUES ($1, $2) RETURNING media_id', media_id, media_hash)

    if filename is not None:
        symlink = media_class.get_symlink_path(base_path=config.link_path, filename=filename)
        os.link(fp, symlink)
        await db.execute('INSERT INTO cdn.links VALUES ($1, $2, $3)', media_id, symlink, media_class.ttl)
    return media_id
