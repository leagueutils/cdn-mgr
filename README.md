# CDN Manager
A database-informed service that handles storing, lifecycle management and provisioning of assets

## Planned storage layout
Assets go to /cdn sub-folders based on their media type:
- images go to cdn/images
- fonts go to cdn/fonts
They are stored with their UUID media_id as the filename (plus filetype extension).

The current sub-folder logic needs to be reworked to give control to the CDN manager
Target architecture: `/assets/{media-class}/{id}[-{name}]/symlink`
