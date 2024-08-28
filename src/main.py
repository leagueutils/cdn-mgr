import asyncio

from cdn import mesh

if __name__ == '__main__':
    asyncio.run(mesh.listen())
