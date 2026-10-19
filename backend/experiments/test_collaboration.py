"""Exercise shared notes over two independent WebSocket connections."""

import asyncio
import os
from unittest.mock import patch

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase

from MLFlowPro.asgi import application
from .models import CollaborationNote


class CollaborationTests(TransactionTestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {"MLFLOWPRO_AI_ACCESS_CODE": "notes-test-code"})
        environment.start()
        self.addCleanup(environment.stop)

    def connection(self, origin="http://127.0.0.1:8000"):
        return WebsocketCommunicator(application, "/ws/experiment-notes/", headers=[
            (b"origin", origin.encode()),
        ])

    async def authenticate(self, socket):
        connected, _ = await socket.connect()
        self.assertTrue(connected)
        await socket.send_json_to({"type": "authenticate", "access_code": "notes-test-code"})
        data = await socket.receive_json_from()
        self.assertEqual(data["type"], "ready")
        return data["document"]

    def test_two_clients_receive_the_same_saved_note_and_reconnect_keeps_it(self):
        async def scenario():
            first, second, third = self.connection(), self.connection(), self.connection()
            try:
                initial = await self.authenticate(first)
                await self.authenticate(second)
                await first.send_json_to({"type": "save", "body": "Compare C=1 and C=2 with training CV.",
                                          "revision": initial["revision"], "request_id": "save-1"})
                one, two = await asyncio.gather(first.receive_json_from(), second.receive_json_from())
                self.assertEqual(one["document"], two["document"])
                self.assertEqual(one["document"]["revision"], 1)
                self.assertTrue(one["own_save"])
                self.assertFalse(two["own_save"])
                restored = await self.authenticate(third)
                self.assertEqual(restored, one["document"])
            finally:
                await first.disconnect()
                await second.disconnect()
                await third.disconnect()
        async_to_sync(scenario)()
        self.assertEqual(CollaborationNote.objects.count(), 1)

    def test_stale_save_is_rejected_and_does_not_overwrite_newer_notes(self):
        async def scenario():
            first, second = self.connection(), self.connection()
            try:
                await self.authenticate(first)
                await self.authenticate(second)
                await first.send_json_to({"type": "save", "body": "First draft", "revision": 0})
                await first.receive_json_from()
                await second.receive_json_from()
                await second.send_json_to({"type": "save", "body": "Old competing draft", "revision": 0})
                conflict = await second.receive_json_from()
                self.assertEqual(conflict["type"], "conflict")
                self.assertEqual(conflict["document"]["body"], "First draft")
                self.assertEqual(conflict["document"]["revision"], 1)
            finally:
                await first.disconnect()
                await second.disconnect()
        async_to_sync(scenario)()
        self.assertEqual(CollaborationNote.objects.get(key="team").body, "First draft")

    def test_wrong_access_code_cannot_read_notes(self):
        async def scenario():
            socket = self.connection()
            try:
                self.assertTrue((await socket.connect())[0])
                await socket.send_json_to({"type": "authenticate", "access_code": "wrong"})
                self.assertEqual((await socket.receive_json_from())["type"], "error")
                self.assertEqual((await socket.receive_output())["code"], 1008)
            finally:
                await socket.disconnect()
        async_to_sync(scenario)()
        self.assertEqual(CollaborationNote.objects.count(), 0)

    def test_missing_access_code_configuration_fails_closed(self):
        with patch.dict(os.environ, {"MLFLOWPRO_AI_ACCESS_CODE": ""}):
            self.test_wrong_access_code_cannot_read_notes()

    def test_untrusted_browser_origin_is_rejected(self):
        async def scenario():
            socket = self.connection("https://untrusted.example")
            try:
                self.assertFalse((await socket.connect())[0])
            finally:
                await socket.disconnect()
        async_to_sync(scenario)()

    def test_invalid_updates_do_not_change_the_document(self):
        async def scenario():
            socket = self.connection()
            try:
                await self.authenticate(socket)
                for payload in [
                    {"type": "save", "body": "x" * 4001, "revision": 0},
                    {"type": "save", "body": "Bad revision", "revision": True},
                    {"type": "save", "body": 1, "revision": 0},
                    {"type": "unknown"}, ["not an object"],
                ]:
                    await socket.send_json_to(payload)
                    self.assertEqual((await socket.receive_json_from())["type"], "error")
                await socket.send_json_to({"type": "load"})
                current = (await socket.receive_json_from())["document"]
                self.assertEqual(current["body"], "")
                self.assertEqual(current["revision"], 0)
                await socket.send_json_to({"type": "ping"})
                self.assertEqual((await socket.receive_json_from())["type"], "pong")
            finally:
                await socket.disconnect()
        async_to_sync(scenario)()
