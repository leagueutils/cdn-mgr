import aiofiles
from aiofiles import os

import leagueutils.models.cdn as cdn_models
import leagueutils.models.mesh as models
from leagueutils.components.logging import get_logger
from leagueutils.components.mesh import RMQMessageService
from leagueutils.errors import DbNotFoundException, MediaNotFound
from leagueutils.models import routes
from leagueutils.models.cdn import ImagePlaceholder, TextComponent
from rust_image_gen import generate_image, generate_mock
from triggers import CronTrigger

from .media_classes import MediaClass, Template
from .subroutines import config, db, delete_media, rust_component_converter, store_components, store_media

# todo: fill these
DEFAULT_FONT_PATH = ''
FALLBACK_FONTS = []


mesh = RMQMessageService(models.ClientConfig())
logger = get_logger()


@mesh.message_mapping(routes.CDN.STORE_MEDIA)
async def add_media(media_bytes: bytes, media_class: str, filename: str | None):
    """store a medium under a given name in the cdn
    :param media_bytes: a byte stream containing the medium to be stored
    :param media_class: the class of the medium
    :param filename: the target name for the symlink. Format: filename.extension
    """

    medium = MediaClass.from_class_name(media_class)
    medium.validate(media_bytes)

    await store_media(medium, media_bytes, filename)


@mesh.message_mapping(routes.CDN.DELETE_MEDIA)
async def remove_media(media_class: str, filename: str):
    """remove a medium from the cdn. Deletes the symlink associated with the request, and if the medium is no
    longer associated with any other links, also deletes the original file
    :param media_class: the class of the medium
    :param filename: the target name. Format: filename.extension
    """

    medium = MediaClass.from_class_name(media_class)
    symlink = medium.get_symlink_path(base_path=config.link_path, filename=filename)

    await delete_media(medium, symlink)


@mesh.message_mapping(routes.CDN.RETRIEVE_MEDIA)
async def retrieve_media(media_class: str, filename: str) -> bytes:
    """retrieve the contents of a medium as a bytes array
    :param media_class:  the class of the medium
    :param filename: the target name. Format: filename.extension
    :return: the file contents
    """

    medium = MediaClass.from_class_name(media_class)
    symlink = medium.get_symlink_path(base_path=config.link_path, filename=filename)
    try:
        async with aiofiles.open(symlink, 'rb') as infile:
            return await infile.read()
    except OSError as e:
        raise MediaNotFound('No such file') from e


@mesh.message_mapping(routes.CDN.CREATE_TEMPLATE)
async def create_template(
    template_type: str,
    tournament_id: int,
    background_image: bytes,
    placeholders: list[cdn_models.ImagePlaceholder | cdn_models.TextPlaceholder],
):
    """create a new template with the given specifications
    :param template_type: the template type
    :param tournament_id: the id of the tournament the template is for
    :param background_image: the background image for the template
    :param placeholders: a list of placeholder component specifications
    """

    # validate image size & file type
    template = Template()
    template.validate(background_image)

    template_id = await store_media(template, background_image, f'{tournament_id}-{template_type}.png')
    await remove_template(template_type, tournament_id)
    await db.execute('INSERT INTO gfx.templates VALUES ($1, $2, $3)', template_id, template_type, tournament_id)

    await store_components(template_id, placeholders)


@mesh.message_mapping(routes.CDN.UPDATE_TEMPLATE)
async def update_template(
    template_type: str,
    tournament_id: int,
    placeholders: list[cdn_models.ImagePlaceholder | cdn_models.TextPlaceholder],
):
    """edit the configuration of an existing template
    :param template_type: the template type
    :param tournament_id: the id of the tournament the template is for
    :param placeholders: a list of placeholder component specifications
    """

    try:
        template_id = await db.fetchrow(
            'SELECT template_id FORM gfx.templates WHERE tournament_id=$1 AND template_type=$2',
            tournament_id,
            template_type,
        )
    except DbNotFoundException as e:
        raise MediaNotFound(f'No {template_type} template for tournament with id {tournament_id}') from e

    await store_components(template_id, placeholders)


@mesh.message_mapping(routes.CDN.DELETE_TEMPLATE)
async def remove_template(template_type: str, tournament_id: int):
    """remove a template
    :param template_type: the template type
    :param tournament_id: the id of the tournament the template is for
    """

    try:
        [media_id] = await db.fetchrow(
            """WITH deleted AS (DELETE FROM gfx.templates WHERE tournament_id=$1 AND template_type=$2 RETURNING
            template_id) SELECT template_id FROM deleted""",
            tournament_id,
            template_type,
        )
    except DbNotFoundException as e:
        raise MediaNotFound(f'No {template_type} template for tournament with id {tournament_id}') from e

    await os.unlink(Template.get_storage_path(config.base_path, media_id))
    await db.execute('DELETE FROM cdn.media WHERE media_id=$1', media_id)


@mesh.message_mapping(routes.CDN.GET_TEMPLATE)
async def fetch_template(
    template_type: str, tournament_id: int
) -> tuple[str, str, list[cdn_models.ImagePlaceholder, cdn_models.TextPlaceholder]]:
    """get a template and its placeholders
    :param template_type: the template type
    :param tournament_id: the tournament it is registered in
    :return: the template id (media id of the background), font filepath and a list of placeholders
    """

    try:
        [font_path] = await db.fetchrow('SELECT font_path FROM gfx.fonts WHERE tournament_id=$1', tournament_id)
    except DbNotFoundException:
        font_path = DEFAULT_FONT_PATH

    try:
        records = await db.fetch(
            """SELECT c.template_id, c.component_type, c.component_value FROM
            gfx.template_components c JOIN gfx.templates t USING(template_id) WHERE t.tournament_id=$1 AND
            t.template_type=$2""",
            tournament_id,
            template_type,
        )
    except DbNotFoundException as e:
        raise MediaNotFound(f'No {template_type} template for tournament with id {tournament_id}') from e

    components = []
    for record in records:
        if record['component_type'] == 'image':
            components.append(ImagePlaceholder(**record['component_value']))
        else:
            components.append(TextComponent(**record['component_value']))

    return records[0]['template_id'], font_path, components  # noqa - the database records are VARCHARs


@mesh.message_mapping(routes.CDN.CREATE_GRAPHICS)
async def create_graphic(template: cdn_models.CompiledGraphicsTemplate) -> bytes:
    """generate an image based on the provided template specifications
    :param template: the compiled template
    :return: a byte stream containing the generated image
    """

    images, text, _ = rust_component_converter(template.components)
    return generate_image(
        Template.get_storage_path(config.base_path, template.media_id),
        images,
        text,
        [template.font_name, *FALLBACK_FONTS],
    )


@mesh.message_mapping(routes.CDN.MOCK_GRAPHICS)
async def create_mockup(template: cdn_models.CompiledGraphicsTemplate) -> bytes:
    """generate a mockup with all components blanked out according to the template specifications
    :param template: the compiled template
    :return: a byte stream containing the generated mockup
    """

    _, _, blanks = rust_component_converter(template.components)
    return generate_mock(Template.get_storage_path(config.base_path, template.media_id), blanks)


@CronTrigger(cron_schedule='0 3 * * *', on_startup=False, logger=logger)  # run at 3:00 AM every day
async def cleanup_expired_assets():
    """remove assets whose time-to-live has passed"""

    try:
        to_remove = await db.fetch(
            """SELECT m.media_class, l.link from cdn.links l JOIN cdn.media m USING(media_id)
            WHERE l.ttl < CURRENT_TIMESTAMP"""
        )
    except DbNotFoundException:
        return  # nothing to clean up

    for media_class, link in to_remove:
        medium = MediaClass.from_class_name(media_class)
        await delete_media(medium, link)
