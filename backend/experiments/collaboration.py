"""Private, revision-checked experiment notes over WebSockets."""

import asyncio
import os
from secrets import compare_digest

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import CollaborationNote


def serialize(note):
    return {"body": note.body, "revision": note.revision,
            "updated_at": note.updated_at.isoformat()}


@database_sync_to_async
def load_document():
    note, _ = CollaborationNote.objects.get_or_create(key="team")
    return serialize(note)


@database_sync_to_async
def save_document(body, revision):
    CollaborationNote.objects.get_or_create(key="team")
    with transaction.atomic():
        changed = CollaborationNote.objects.filter(key="team", revision=revision).update(
            body=body, revision=F("revision") + 1, updated_at=timezone.now(),
        )
        return bool(changed), serialize(CollaborationNote.objects.get(key="team"))


class ExperimentNotesConsumer(AsyncJsonWebsocketConsumer):
    group_name = "mlflowpro-experiment-notes"
    authentication_timeout = 10

    async def connect(self):
        self.authorized = False
        self.auth_timer = None
        await self.accept()
        self.auth_timer = asyncio.create_task(self.expire_unauthenticated_connection())

    async def expire_unauthenticated_connection(self):
        await asyncio.sleep(self.authentication_timeout)
        if not self.authorized:
            await self.close(code=1008)

    async def receive_json(self, content, **kwargs):
        if not isinstance(content, dict):
            await self.send_json({"type": "error", "error": "Send a JSON object."})
            return
        if not self.authorized:
            code = os.environ.get("MLFLOWPRO_AI_ACCESS_CODE", "").strip()
            supplied = content.get("access_code")
            if (content.get("type") != "authenticate" or not code
                    or not isinstance(supplied, str) or len(supplied) > 512
                    or not compare_digest(code.encode(), supplied.encode())):
                await self.send_json({"type": "error", "error": "The team access code was not accepted."})
                await self.close(code=1008)
                return
            self.authorized = True
            if self.auth_timer:
                self.auth_timer.cancel()
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.send_json({"type": "ready", "document": await load_document()})
            return

        if content.get("type") == "ping":
            await self.send_json({"type": "pong"})
            return
        if content.get("type") == "load":
            await self.send_json({"type": "document", "document": await load_document()})
            return
        if content.get("type") != "save":
            await self.send_json({"type": "error", "error": "Unknown notes action."})
            return

        body = content.get("body")
        revision = content.get("revision")
        request_id = content.get("request_id", "")
        if (not isinstance(body, str) or len(body) > 4000
                or type(revision) is not int or revision < 0
                or not isinstance(request_id, str) or len(request_id) > 64):
            await self.send_json({"type": "error", "error": "Notes must be at most 4,000 characters with a valid revision."})
            return
        saved, document = await save_document(body, revision)
        if not saved:
            await self.send_json({"type": "conflict", "document": document, "request_id": request_id})
            return
        await self.channel_layer.group_send(self.group_name, {
            "type": "notes.updated", "document": document,
            "request_id": request_id, "sender": self.channel_name,
        })

    async def notes_updated(self, event):
        await self.send_json({
            "type": "document", "document": event["document"],
            "request_id": event["request_id"], "own_save": event["sender"] == self.channel_name,
        })

    async def disconnect(self, close_code):
        if self.auth_timer:
            self.auth_timer.cancel()
        if self.authorized:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
