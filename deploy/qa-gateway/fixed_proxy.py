"""固定本地应用的流式HTTP转发，不提供动态URL、CONNECT或日志。"""
import asyncio


async def serve():
    async def handle(reader, writer):
        target = None
        try:
            incoming, target = await asyncio.wait_for(asyncio.open_connection('172.30.250.10', 8180), 5)
            async def copy(source, destination):
                while data := await asyncio.wait_for(source.read(65536), 120):
                    destination.write(data)
                    await destination.drain()
            tasks = [asyncio.create_task(copy(reader, target)), asyncio.create_task(copy(incoming, writer))]
            _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        except (OSError, asyncio.TimeoutError):
            pass
        finally:
            if target:
                target.close()
            writer.close()
    server = await asyncio.start_server(handle, '0.0.0.0', 8180)
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    asyncio.run(serve())
