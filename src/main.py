import asyncio

from service import mesh

from triggers import start_triggers

if __name__ == '__main__':
    asyncio.run(start_triggers())
    asyncio.run(mesh.listen())
