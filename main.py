import asyncio
from leagueutils.models.cdn import Config

# local imports
from cdn import CDNManager


cdn_mgr = CDNManager(Config())

if __name__ == '__main__':
    asyncio.run(cdn_mgr.run())
