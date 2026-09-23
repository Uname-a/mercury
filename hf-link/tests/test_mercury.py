import asyncio
import unittest

from hf_link.mercury import MercuryClient


class MercuryClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_event_does_not_replace_command_response(self) -> None:
        events = []

        async def control(reader, writer):
            command = await reader.readuntil(b"\r")
            self.assertEqual(command, b"MYCALL N0CALL\r")
            writer.write(b"OK\rREGISTERED N0CALL\r")
            await writer.drain()
            command = await reader.readuntil(b"\r")
            self.assertEqual(command, b"BW500\r")
            writer.write(b"OK\r")
            await writer.drain()
            command = await reader.readuntil(b"\r")
            self.assertEqual(command, b"LISTEN ON\r")
            writer.write(b"OK\r")
            await writer.drain()
            await reader.read()
            writer.close()

        async def data(reader, writer):
            await reader.read()
            writer.close()

        control_server = await asyncio.start_server(control, "127.0.0.1", 0)
        port = control_server.sockets[0].getsockname()[1]
        data_server = await asyncio.start_server(data, "127.0.0.1", port + 1)
        async with control_server, data_server:
            client = MercuryClient("127.0.0.1", port)
            await client.open()
            await client.initialize("N0CALL")

            async def one_event():
                async for event in client.events():
                    events.append(event)
                    return

            await asyncio.wait_for(one_event(), 1)
            await client.close()
        self.assertEqual(events, ["REGISTERED N0CALL"])


if __name__ == "__main__":
    unittest.main()
