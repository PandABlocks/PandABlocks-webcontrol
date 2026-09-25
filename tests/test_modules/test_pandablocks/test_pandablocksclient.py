import asyncio
import inspect
import socket
import unittest
from collections import OrderedDict
from unittest.mock import call, patch

from malcolm.core import Spawned
from malcolm.modules.pandablocks.pandablocksclient import (
    BlockData,
    FieldData,
    PandABlocksClient,
)

from ...loop import on_loop


class FakeWriter:
    """Stands in for the StreamWriter of a connection to a PandA

    Records what was sent, and gives the reader its EOF when closed, the way
    the far end going away would.
    """

    def __init__(self, reader):
        self._reader = reader
        self.written = []

    def write(self, data):
        self.written.append(call(data))

    async def drain(self):
        pass

    def close(self):
        self._reader.feed_eof()

    async def wait_closed(self):
        pass


class PandABoxControlTest(unittest.TestCase):
    def setUp(self):
        self.c = PandABlocksClient("h", "p")

    async def start(self, messages=None):
        if messages is None:
            messages = []
        elif not isinstance(messages, list):
            messages = [messages]

        async def open_connection(hostname, port, **kwargs):
            # Made on the event loop, which is where the client reads it from
            reader = asyncio.StreamReader()
            for message in messages:
                reader.feed_data(message.encode("utf-8"))
            self.writer = FakeWriter(reader)
            return reader, self.writer

        self.patch = patch(
            "malcolm.modules.pandablocks.pandablocksclient.asyncio.open_connection",
            open_connection,
        )
        self.patch.start()
        self.addCleanup(self.patch.stop)
        await self.c.start(lambda func: Spawned(func, (), {}))

    @property
    def written(self):
        return self.writer.written

    def assert_written_once(self, data):
        assert self.written == [call(data)]

    def tearDown(self):
        if self.c.started:
            Spawned(self.c.stop, (), {}).get(10)

    def test_send_and_recv_loops_are_coroutines(self):
        # They are awaited on the event loop rather than each taking a thread,
        # so they must stay coroutine functions
        assert inspect.iscoroutinefunction(PandABlocksClient._send_loop)
        assert inspect.iscoroutinefunction(PandABlocksClient._recv_loop)

    @on_loop
    async def test_connect_failure_raises_connection_error(self):
        # Bind a port, then drop it, so there is nothing listening there
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        c = PandABlocksClient("127.0.0.1", port)
        with self.assertRaises(ConnectionError) as cm:
            await c.start(lambda func: Spawned(func, (), {}))
        assert "did all services on the PandA start correctly?" in str(cm.exception)
        assert c.started is False

    @on_loop
    async def test_stop_then_start_again(self):
        await self.start(["OK =1\n"])
        assert await self.c.send_recv("") == "OK =1"
        await self.c.stop()
        assert self.c.started is False
        await self.start(["OK =2\n"])
        assert await self.c.send_recv("") == "OK =2"
        assert self.written == [call(b"")]

    @on_loop
    async def test_multiline_response_good(self):
        messages = ["!TTLIN 6\n", "!OUTENC 4\n!CAL", "C 2\n.\nblah"]
        await self.start(messages)
        resp = list(await self.c.send_recv(""))
        await self.c.stop()
        expected = ["TTLIN 6", "OUTENC 4", "CALC 2"]
        assert resp == expected

    @on_loop
    async def test_two_resp(self):
        messages = ["OK =mm\n", "OK =232\n"]
        await self.start(messages)
        assert await self.c.send_recv("") == "OK =mm"
        assert await self.c.send_recv("") == "OK =232"

    @on_loop
    async def test_bad_good(self):
        messages = ["ERR Invalid bit value\n", "OK =232\n"]
        await self.start(messages)
        with self.assertRaises(ValueError):
            await self.c.send_recv("")
        assert await self.c.send_recv("") == "OK =232"

    @on_loop
    async def test_block_data(self):
        messages = [
            "!TTLIN 6\n!TTLOUT 10\n.\n",
            "OK =TTL input\n",
            "OK =TTL output\n",
            "!VAL 1 ext_out funny\n!TERM 0 param enum\n.\n",
            "!VAL 0 bit_mux\n.\n",
            "OK =TTL termination\n",
            "OK =TTL input value\n",
            "!High-Z\n!50-Ohm\n.\n",
            "!No\n!Value\n.\n",
            "OK =TTL output value\n",
            "!ZERO\n!TTLIN1.VAL\n!TTLIN2.VAL\n.\n",
        ]
        await self.start(messages)
        block_data = await self.c.get_blocks_data()
        await self.c.stop()
        assert self.written == [
            call(b"*BLOCKS?\n"),
            call(b"*DESC.TTLIN?\n"),
            call(b"*DESC.TTLOUT?\n"),
            call(b"TTLIN.*?\n"),
            call(b"TTLOUT.*?\n"),
            call(b"*DESC.TTLIN.TERM?\n"),
            call(b"*DESC.TTLIN.VAL?\n"),
            call(b"*ENUMS.TTLIN.TERM?\n"),
            call(b"*ENUMS.TTLIN.VAL.CAPTURE?\n"),
            call(b"*DESC.TTLOUT.VAL?\n"),
            call(b"*ENUMS.TTLOUT.VAL?\n"),
        ]
        assert list(block_data) == ["TTLIN", "TTLOUT"]
        in_fields = OrderedDict()
        in_fields["TERM"] = FieldData(
            "param", "enum", "TTL termination", ["High-Z", "50-Ohm"]
        )
        in_fields["VAL"] = FieldData(
            "ext_out", "funny", "TTL input value", ["No", "Value"]
        )
        assert block_data["TTLIN"] == (BlockData(6, "TTL input", in_fields))
        out_fields = OrderedDict()
        out_fields["VAL"] = FieldData(
            "bit_mux", "", "TTL output value", ["ZERO", "TTLIN1.VAL", "TTLIN2.VAL"]
        )
        assert block_data["TTLOUT"] == (BlockData(10, "TTL output", out_fields))

    @on_loop
    async def test_changes(self):
        messages = [
            """!PULSE0.WIDTH=1.43166e+09
!PULSE1.WIDTH=1.43166e+09
!PULSE2.WIDTH=1.43166e+09
!PULSE3.WIDTH=1.43166e+09
!SEQ1.TABLE<
!PULSE0.INP (error)
!PULSE1.INP (error)
!PULSE2.INP (error)
!PULSE3.INP (error)
.
""",
            """!1
!2
!3
.
""",
        ]
        await self.start(messages)
        changes = list(await self.c.get_changes(include_errors=True))
        await self.c.stop()
        assert self.written == [
            call(b"*CHANGES?\n"),
            call(b"SEQ1.TABLE?\n"),
        ]
        expected = OrderedDict()
        expected["PULSE0.WIDTH"] = "1.43166e+09"
        expected["PULSE1.WIDTH"] = "1.43166e+09"
        expected["PULSE2.WIDTH"] = "1.43166e+09"
        expected["PULSE3.WIDTH"] = "1.43166e+09"
        expected["SEQ1.TABLE"] = ["1", "2", "3"]
        expected["PULSE0.INP"] = Exception
        expected["PULSE1.INP"] = Exception
        expected["PULSE2.INP"] = Exception
        expected["PULSE3.INP"] = Exception
        assert OrderedDict(changes) == expected

    @on_loop
    async def test_get_pcap_bits_fields(self):
        messages = (
            ["!BITS1 1 ext_out bits\n!BITS0 0 ext_out bits\n.\n"]
            + ["!B%d\n" % i for i in range(32)]
            + [".\n"]
            + ["!B%d\n" % i for i in range(32, 52)]
            + ["!\n" * 12]
            + [".\n"]
        )
        await self.start(messages)
        expected = {
            "PCAP.BITS0.CAPTURE": ["B%d" % i for i in range(32)],
            "PCAP.BITS1.CAPTURE": ["B%d" % i for i in range(32, 52)] + [""] * 12,
        }
        assert await self.c.get_pcap_bits_fields() == expected
        await self.c.stop()
        assert self.written == [
            call(b"PCAP.*?\n"),
            call(b"PCAP.BITS0.BITS?\n"),
            call(b"PCAP.BITS1.BITS?\n"),
        ]

    @on_loop
    async def test_get_field(self):
        messages = "OK =32\n"
        await self.start(messages)
        assert await self.c.get_field("PULSE0", "WIDTH") == "32"
        await self.c.stop()
        self.assert_written_once(b"PULSE0.WIDTH?\n")

    @on_loop
    async def test_set_field(self):
        messages = "OK\n"
        await self.start(messages)
        await self.c.set_field("PULSE0", "WIDTH", 0)
        await self.c.stop()
        self.assert_written_once(b"PULSE0.WIDTH=0\n")

    @on_loop
    async def test_set_fields(self):
        messages = "OK\nOK\n"
        await self.start(messages)
        await self.c.set_fields({"PULSE0.WIDTH": 0, "PULSE0.DELAY": 5})
        await self.c.stop()
        assert sorted(self.written) == [
            call(b"PULSE0.DELAY=5\n"),
            call(b"PULSE0.WIDTH=0\n"),
        ]

    @on_loop
    async def test_set_table(self):
        messages = "OK\n"
        await self.start(messages)
        await self.c.set_table("SEQ1", "TABLE", [1, 2, 3])
        await self.c.stop()
        self.assert_written_once(
            b"""SEQ1.TABLE<
1
2
3

"""
        )

    @on_loop
    async def test_table_fields(self):
        messages = [
            """!31:0    REPEATS
!32:32   USE_INPA
!64:54  STUFF
!38:37   INPB enum
.
""",
            """!None
!First
!Second
.
""",
            "OK =Repeats\n",
            "OK =Use\n",
            "OK =Stuff\n",
            "OK =Inp B\n",
        ]
        await self.start(messages)
        fields = await self.c.get_table_fields("SEQ1", "TABLE")
        await self.c.stop()
        assert self.written == [
            call(b"SEQ1.TABLE.FIELDS?\n"),
            call(b"*ENUMS.SEQ1.TABLE[].INPB?\n"),
            call(b"*DESC.SEQ1.TABLE[].REPEATS?\n"),
            call(b"*DESC.SEQ1.TABLE[].USE_INPA?\n"),
            call(b"*DESC.SEQ1.TABLE[].STUFF?\n"),
            call(b"*DESC.SEQ1.TABLE[].INPB?\n"),
        ]
        expected = OrderedDict()
        expected["REPEATS"] = (31, 0, "Repeats", None, False)
        expected["USE_INPA"] = (32, 32, "Use", None, False)
        expected["STUFF"] = (64, 54, "Stuff", None, False)
        expected["INPB"] = (38, 37, "Inp B", ["None", "First", "Second"], False)
        assert fields == expected
