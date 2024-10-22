import uuid

import aiofiles
from aiofiles import os

import leagueutils.models.cdn as cdn_models
from leagueutils.components.db import DBService
from leagueutils.errors import CDNException, DbNotFoundException
from rust_image_gen import Color, ImageComponent, Offset, Size, TextAlignment, TextComponent

from .media_classes import MediaClass

config = cdn_models.Config()
db = DBService()


async def delete_media(media_class: MediaClass, symlink: str):
    """subroutine to clean up a medium by symlink"""

    try:
        await os.unlink(symlink)
        [media_id] = await db.fetchrow('DELETE FROM cdn.links WHERE link=$1 RETURNING media_id', symlink)
    except (DbNotFoundException, FileNotFoundError) as e:  # no linked image
        raise CDNException(code=404, message='No such file') from e

    [other_links] = await db.fetchrow('SELECT COUNT(*) FROM cdn.links WHERE media_id=$1')
    if other_links == 0:
        await os.unlink(media_class.get_storage_path(config.base_path, media_id, symlink.split('.')[-1]))
        await db.execute('DELETE FROM cdn.media WHERE media_id=$1', media_id)


async def store_media(media_class: MediaClass, media_bytes: bytes, filename: str) -> str:
    """subroutine to store a medium"""

    media_hash = media_class.hash(media_bytes)
    try:
        [media_id] = await db.fetchrow('SELECT media_id FROM cdn.media WHERE hash=$1', media_hash)
        store = False
    except DbNotFoundException:
        store = True
        media_id = str(uuid.uuid4())

    extension = filename.split('.')[-1]
    fp = media_class.get_storage_path(base_path=config.base_path, media_id=media_id, extension=extension)
    if store:
        async with aiofiles.open(fp, 'wb+') as outfile:
            await outfile.write(media_bytes)
        await db.execute('INSERT INTO cdn.media VALUES ($1, $2) RETURNING media_id', media_id, media_hash)

    symlink = media_class.get_symlink_path(base_path=config.link_path, filename=filename)
    await os.link(fp, symlink)
    await db.execute('INSERT INTO cdn.links VALUES ($1, $2, $3)', media_id, symlink, media_class.ttl)
    return media_id


async def store_components(template_id: str, components: [cdn_models.ImagePlaceholder | cdn_models.TextPlaceholder]):
    """subroutine to store components for a template"""

    data = []
    for component in components:
        data.append(
            (
                template_id,
                'image' if isinstance(component, cdn_models.ImagePlaceholder) else 'text',
                component.model_dump(),
            )
        )
    await db.execute('INSERT INTO gfx.template_components VALUES ($1, $2, $3)', data)


def rust_component_converter(
    components: list[cdn_models.BlankComponent, cdn_models.ImageComponent, cdn_models.TextComponent],
) -> tuple[list[ImageComponent], list[TextComponent]]:
    """convert a list of models into Rust-compatible classes"""

    images, text = [], []
    for component in components:
        model = component.model_dump()
        for name, value in model.items():  # convert sub-classes
            if isinstance(value, dict):
                match name:
                    case 'offset':
                        model[name] = Offset(**value)
                    case 'size':
                        model[name] = Size(**value)
                    case 'color':
                        model[name] = Color(**value)
                    case 'text_align':
                        model[name] = TextAlignment(**value)

        match component.__class__.__name__:
            case 'ImageComponent':
                model['file_path'] = MediaClass.from_class_name(
                    cdn_models.MediaClass(model.pop('media_class'))
                ).get_symlink_path(config.link_path, model.pop('file_name'))
                images.append(ImageComponent(**model))
            case 'TextComponent':
                text.append(TextComponent(**model))

    return images, text
