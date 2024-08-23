import aiofiles
import os
import uuid
from typing import Optional

from leagueutils.components import db
from leagueutils.components.mesh import MessageService, routes
from leagueutils.errors import CDNError, MediaNotFound, NotFoundException
from leagueutils.models.cdn import Config

from media_classes import MediaClass


mesh = MessageService()


class CDNManager:
    """
    storage layout
        assets go to /cdn sub-folders based on their media type
            images go to cdn/images
            fonts go to cdn/fonts
        they are stored with their UUID media_id as the filename (plus filetype extension)

        current sub-folder logic needs to be reworked to give control to the cdn manager
        target architecture:
        /assets/{media-class}/{id}[-{name}]/symlink
    """
    def __init__(self, config: Config):
        self.base_path = config.base_path
        self.link_path = config.link_path

    @mesh.message_mapping(routes.CDN.STORE_MEDIA_REQUEST)
    async def add_media(self, media_bytes: bytes, media_class: str, name: str):
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

        fp = self.get_storage_path(medium, media_id)
        if store:
            await self.store_media(media_bytes, fp)
            await db.execute('INSERT INTO cdn.media VALUES ($1, $2) RETURNING media_id', media_id, media_hash)
        symlink = self.get_symlink(media_class, name)
        os.link(fp, symlink)
        await db.execute('INSERT INTO cdn.links VALUES ($1, $2, $3)', media_id, symlink, medium.ttl)

    async def add_link(self, target_link: str, media_id: Optional[str], source_link: Optional[str],
                       media_class: Optional[str]):
        # todo: investigate injecting utility methods via a sidecar class that is statically passed
        if source_link:
            try:
                [media_id] = await db.fetchrow('SELECT media_id FROM cdn.links WHERE link=$1', source_link)
            except NotFoundException:
                raise MediaNotFound(f'Could not find media for link {source_link}')
        elif not media_id:
            raise CDNError('Media ID or source link must be provided')

        if not media_class:
            [media_class] = await db.fetchrow('SELECT media_class FROM cdn.media WHERE media_id=$1', media_id)
        medium = MediaClass.from_class_name(media_class, target_link)
        fp = self.get_storage_path(media_class, media_id)
        os.symlink(fp, target_link)
        await db.execute('INSERT INTO cdn.links VALUES ($1, $2, $3)', media_id, target_link, medium.ttl)

    def get_symlink(self, media_class: str, name: str):
        # todo: figure out how to deal with the current folder structure
        return os.path.join(self.link_path, media_class, name)

    def get_storage_path(self, medium: MediaClass, media_id) -> str:
        return medium.storage_path_template.format(base_path=self.base_path, media_id=media_id)

    @staticmethod
    async def store_media(media_bytes: bytes, fp: str):
        async with aiofiles.open(fp, 'wb+') as fh:
            await fh.write(media_bytes)

    @mesh.message_mapping(routes.CDN.DELETE_MEDIA_REQUEST)
    async def remove_media(self, media_class: str, name: Optional[str] = None, link: Optional[str] = None):
        """remove a medium from the cdn. Deletes the symlink associated with the request, and if the medium is no
        longer associated with any other links, also deletes the original file
        :param media_class: the class of the medium
        :param name: the target name. Format: tournament_id-tournament_name/filename.extension
        :param link: the symlink to delete
        """
        if link:
            symlink = link
        elif name:
            symlink = self.get_symlink(media_class, name)
        else:
            raise CDNError('link or name must be provided')

        medium = MediaClass.from_class_name(media_class, symlink)

        try:
            os.unlink(symlink)
            [media_id] = await db.fetchrow('DELETE FROM cdn.links WHERE link=$1 RETURNING media_id', symlink)
        except (NotFoundException, FileNotFoundError):  # no linked image
            return

        [other_links] = await db.fetchrow('SELECT COUNT(*) FROM cdn.links WHERE media_id=$1')
        if other_links == 0:
            os.unlink(self.get_storage_path(medium, media_id))
            await db.execute('DELETE FROM cdn.media WHERE media_id=$1', media_id)

    async def cleanup_expired_assets(self):  # todo: run periodically
        try:
            to_remove = await db.fetch('''SELECT m.media_class, l.link from cdn.links l JOIN cdn.media m USING(media_id)
                WHERE l.ttl < CURRENT_TIMESTAMP''')
        except NotFoundException:
            return  # nothing to clean up
        
        for media_class, link in to_remove:
            await self.remove_media(media_class, link)

    @staticmethod
    async def run():
        await mesh.listen()