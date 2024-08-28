import os

from media_classes import MediaClass

from leagueutils.models.cdn import Config

config = Config()


def get_symlink(media_class: str, name: str):
    # todo: figure out how to deal with the current folder structure
    return os.path.join(config.link_path, media_class, name)


def get_storage_path(medium: MediaClass, media_id) -> str:
    return medium.storage_path_template.format(base_path=config.base_path, media_id=media_id)
