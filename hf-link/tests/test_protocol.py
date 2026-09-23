import struct
import unittest

from hf_link.protocol import FrameDecoder, HEADER, MAGIC, MAX_FRAME_BYTES, ProtocolError, VERSION, encode_frame


class FrameTests(unittest.TestCase):
    def test_round_trip_with_partial_reads(self) -> None:
        expected = {"type": "TEXT", "id": b"1234567890123456", "body": "hello", "n": 4}
        encoded = encode_frame(expected)
        decoder = FrameDecoder()
        actual = []
        for byte in encoded:
            actual.extend(decoder.feed(bytes((byte,))))
        self.assertEqual(actual, [expected])

    def test_coalesced_frames(self) -> None:
        decoder = FrameDecoder()
        self.assertEqual(
            decoder.feed(encode_frame({"n": 1}) + encode_frame({"n": 2})),
            [{"n": 1}, {"n": 2}],
        )

    def test_oversized_announced_frame_is_rejected_before_body(self) -> None:
        decoder = FrameDecoder()
        header = HEADER.pack(MAGIC, VERSION, MAX_FRAME_BYTES + 1)
        with self.assertRaisesRegex(ProtocolError, "exceeds"):
            decoder.feed(header)

    def test_unknown_version_is_rejected(self) -> None:
        decoder = FrameDecoder()
        with self.assertRaisesRegex(ProtocolError, "version"):
            decoder.feed(struct.pack(">4sBI", MAGIC, VERSION + 1, 0))

    def test_map_encoding_is_canonical(self) -> None:
        self.assertEqual(encode_frame({"bb": 1, "a": 2}), encode_frame({"a": 2, "bb": 1}))


if __name__ == "__main__":
    unittest.main()

