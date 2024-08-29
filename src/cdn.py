import os
import uuid

import aiofiles
from media_classes import MediaClass

from leagueutils.components import db
from leagueutils.components.mesh import MessageService, routes
from leagueutils.errors import CDNException, NotFoundException
from leagueutils.models.cdn import Config

mesh = MessageService()
config = Config()


@mesh.message_mapping(routes.CDN.STORE_MEDIA)
async def add_media(media_bytes: bytes, media_class: str, filename: str):
    """store a medium in the cdn
    :param media_bytes: a byte stream containing the medium to be stored
    :param media_class: the class of the medium
    :param filename: the target name for the symlink. Format: filename.extension
    """

    medium = MediaClass.from_class_name(media_class)
    media_hash = medium.hash(media_bytes)
    try:
        [media_id] = await db.fetchrow('SELECT media_id FROM cdn.media WHERE hash=$1', media_hash)
        store = False
    except NotFoundException:
        store = True
        media_id = str(uuid.uuid4())

    name, extension = filename.split('.')[-1]
    fp = medium.get_storage_path(base_path=config.base_path, media_id=media_id, extension=extension)
    if store:
        async with aiofiles.open(fp, 'wb+') as outfile:
            await outfile.write(media_bytes)
        await db.execute('INSERT INTO cdn.media VALUES ($1, $2) RETURNING media_id', media_id, media_hash)
    symlink = medium.get_symlink_path(base_path=config.link_path, name=name, extension=extension)
    os.link(fp, symlink)
    await db.execute('INSERT INTO cdn.links VALUES ($1, $2, $3)', media_id, symlink, medium.ttl)


@mesh.message_mapping(routes.CDN.DELETE_MEDIA)
async def remove_media(media_class: str, filename: str):
    """remove a medium from the cdn. Deletes the symlink associated with the request, and if the medium is no
    longer associated with any other links, also deletes the original file
    :param media_class: the class of the medium
    :param filename: the target name. Format: filename.extension
    """

    name, extension = filename.split('.')
    medium = MediaClass.from_class_name(media_class)
    symlink = medium.get_symlink_path(base_path=config.link_path, name=name, extension=extension)

    try:
        os.unlink(symlink)
        [media_id] = await db.fetchrow('DELETE FROM cdn.links WHERE link=$1 RETURNING media_id', symlink)
    except (NotFoundException, FileNotFoundError) as e:  # no linked image
        raise CDNException('No such file') from e

    [other_links] = await db.fetchrow('SELECT COUNT(*) FROM cdn.links WHERE media_id=$1')
    if other_links == 0:
        os.unlink(medium.get_storage_path(config.base_path, media_id, symlink.split('.')[-1]))
        await db.execute('DELETE FROM cdn.media WHERE media_id=$1', media_id)


@mesh.message_mapping(routes.CDN.RETRIEVE_MEDIA)
async def retrieve_media(media_class: str, filename: str) -> bytes:
    """retrieve the contents of a medium as a bytes array
    :param media_class:  the class of the medium
    :param filename: the target name. Format: filename.extension
    :return: the file contents
    """

    name, extension = filename.split('.')
    medium = MediaClass.from_class_name(media_class)
    symlink = medium.get_symlink_path(base_path=config.link_path, name=name, extension=extension)
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
