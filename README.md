# CDN Manager
A database-informed service that handles storing, lifecycle management and provisioning of assets

## Planned storage layout
Assets go into a single, flat folder, regardless of file or media type. They are stored with their UUID media_id as
their filename (plus filetype extension). Each medium will be referred to by one or more symlinks. Symlinks live in a
different domain and are split into sub-folders by media type. Media types tied to a LU entity (e.g. team logos) will
have their symlink named according to the following convention: `entity_id-entity_short_code.extension`. Other media
types will follow their own conventions (or no convention at all, e.g. for fonts)


## Target architecture
- for symlinks: `/assets/{media-class}/{filename}`, e.g. `/assets/tournament-logos/123.png`, `assets/team-logos/456.png`
- for media: `/cdn/{media-id}.{extension}`, e.g. `/cdn/123-abcd.png`


## Interface
The public API of the CDN manager purely works on filenames and media classes. Folder structure, naming, deduplication
and more are handled internally based on this information


## Image Generation
This service also houses infrastructure to generate images from templates and fillers, leveraging a custom-built Rust
crate with Python bindings for maximum speed
