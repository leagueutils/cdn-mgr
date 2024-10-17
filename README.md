# CDN Manager
A database-informed service that handles storing, lifecycle management and provisioning of assets

## Planned storage layout
Assets go to /cdn sub-folders based on their media type:
- images go to cdn/images
- fonts go to cdn/fonts
They are stored with their UUID media_id as the filename (plus filetype extension).

The current sub-folder logic needs to be reworked to give control to the CDN manager


## Target architecture
- for symlinks: `/assets/{media-class}/{filename}`, e.g. `/assets/tournaments/123.png`, `assets/teams/456.png`
- for media: `/cdn/{media-type}/{media-id}.{extension}`, e.g. `/cdn/images/abcd-efgh.png`


## Interface
The public API of the CDN manager purely works on filenames and media classes. Folder structure, naming, deduplication
and more are handled internally based on this information


## Image Generation
This service also houses infrastructure to generate images from templates and fillers, leveraging a custom-built Rust
crate with Python bindings for maximum speed
