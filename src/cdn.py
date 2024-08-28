import os
import uuid

import aiofiles
from media_classes import MediaClass
from subroutines import get_storage_path, get_symlink

from leagueutils.components import db
from leagueutils.components.mesh import MessageService, routes
from leagueutils.errors import CDNException, NotFoundException

mesh = MessageService()


@mesh.message_mapping(routes.CDN.STORE_MEDIA)
async def add_media(media_bytes: bytes, media_class: str, name: str):
    """store a medium in the cdn
    :param media_bytes: a byte stream containing the medium to be stored
    :param media_class: the class of the medium
    :param name: the target name. Format: tournament_id-tournament_name/filename.extension
    """

    medium = MediaClass.from_class_name(media_class, name, media_bytes)
    media_hash = medium.hash()
    try:
        [media_id] = await db.fetchrow('SELECT media_id FROM cdn.media WHERE hash=$1', media_hash)
        store = False
    except NotFoundException:
        store = True
        media_id = str(uuid.uuid4())

    fp = get_storage_path(medium, media_id)
    if store:
        async with aiofiles.open(fp, 'wb+') as outfile:
            await outfile.write(media_bytes)
        await db.execute('INSERT INTO cdn.media VALUES ($1, $2) RETURNING media_id', media_id, media_hash)
    symlink = get_symlink(media_class, name)
    os.link(fp, symlink)
    await db.execute('INSERT INTO cdn.links VALUES ($1, $2, $3)', media_id, symlink, medium.ttl)


@mesh.message_mapping(routes.CDN.DELETE_MEDIA)
async def remove_media(media_class: str, name: str | None = None, link: str | None = None):
    """remove a medium from the cdn. Deletes the symlink associated with the request, and if the medium is no
    longer associated with any other links, also deletes the original file
    :param media_class: the class of the medium
    :param name: the target name. Format: tournament_id-tournament_name/filename.extension
    :param link: the symlink to delete
    """
    if link:
        symlink = link
    elif name:
        symlink = get_symlink(media_class, name)
    else:
        raise CDNException('link or name must be provided')

    medium = MediaClass.from_class_name(media_class, symlink)

    try:
        os.unlink(symlink)
        [media_id] = await db.fetchrow('DELETE FROM cdn.links WHERE link=$1 RETURNING media_id', symlink)
    except (NotFoundException, FileNotFoundError):  # no linked image
        return

    [other_links] = await db.fetchrow('SELECT COUNT(*) FROM cdn.links WHERE media_id=$1')
    if other_links == 0:
        os.unlink(get_storage_path(medium, media_id))
        await db.execute('DELETE FROM cdn.media WHERE media_id=$1', media_id)


@mesh.message_mapping(routes.CDN.RETRIEVE_MEDIA)
async def retrieve_media(media_class: str, name: str | None = None, link: str | None = None) -> bytes:
    if link:
        symlink = link
    elif name:
        symlink = get_symlink(media_class, name)
    else:
        raise CDNException('link or name must be provided')

    try:
        async with aiofiles.open(symlink, 'rb') as infile:
            return await infile.read()
    except OSError as e:
        raise CDNException('No such file') from e


async def cleanup_expired_assets():  # todo: run periodically
    try:
        to_remove = await db.fetch(
            """SELECT m.media_class, l.link from cdn.links l JOIN cdn.media m USING(media_id)
            WHERE l.ttl < CURRENT_TIMESTAMP"""
        )
    except NotFoundException:
        return  # nothing to clean up

    for media_class, link in to_remove:
        await remove_media(media_class, link)
