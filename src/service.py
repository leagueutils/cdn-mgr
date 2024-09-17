import os
import uuid

import aiofiles
from subroutines import _remove_media, config, db

from leagueutils.components.logging import get_logger
from leagueutils.components.mesh import RMQMessageService
from leagueutils.errors import DbNotFoundException, MediaNotFound
from leagueutils.models import routes
from triggers import CronTrigger

from .media_classes import MediaClass

mesh = RMQMessageService()
logger = get_logger()


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
    except DbNotFoundException:
        store = True
        media_id = str(uuid.uuid4())

    name, extension = filename.split('.')
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

    await _remove_media(medium, symlink)


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
        raise MediaNotFound('No such file') from e


@CronTrigger(cron_schedule='0 3 * * *', on_startup=False, logger=logger)  # run at 3:00 AM every day
async def cleanup_expired_assets():
    try:
        to_remove = await db.fetch(
            """SELECT m.media_class, l.link from cdn.links l JOIN cdn.media m USING(media_id)
            WHERE l.ttl < CURRENT_TIMESTAMP"""
        )
    except DbNotFoundException:
        return  # nothing to clean up

    for media_class, link in to_remove:
        medium = MediaClass.from_class_name(media_class)
        await _remove_media(medium, link)
