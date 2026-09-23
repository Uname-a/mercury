from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from hf_link.models import Message, MessageState
from hf_link.storage import MessageStore


class StorageTests(unittest.TestCase):
    def test_persists_and_deduplicates_messages(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "messages.sqlite3"
            first = MessageStore(path)
            message = Message.outgoing("N0CALL", "K1TEST", "hello")
            self.assertTrue(first.put(message))
            self.assertFalse(first.put(message))
            reopened = MessageStore(path)
            self.assertEqual(reopened.get(message.message_id), message)

    def test_validates_state_transitions(self) -> None:
        with TemporaryDirectory() as directory:
            store = MessageStore(Path(directory) / "messages.sqlite3")
            message = Message.outgoing("N0CALL", "K1TEST", "hello")
            store.put(message)
            store.transition(message.message_id, MessageState.CONNECTING)
            self.assertEqual(store.get(message.message_id).state, MessageState.CONNECTING)
            with self.assertRaisesRegex(ValueError, "invalid transition"):
                store.transition(message.message_id, MessageState.PEER_STORED)

    def test_rejects_oversized_text(self) -> None:
        with self.assertRaisesRegex(ValueError, "4096"):
            Message.outgoing("N0CALL", "K1TEST", "x" * 4097)


if __name__ == "__main__":
    unittest.main()
