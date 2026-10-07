import json
import logging

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def get_group_name(user_pk):
    return 'notif-' + str(user_pk)


def get_room_name(cls, pk):
    return "room-%s-%d" % (cls, pk)


def send_event(cls, pk, event_name, data):
    channel_layer = get_channel_layer()
    try:
        async_to_sync(channel_layer.group_send)(
            get_room_name(cls, pk),
            {'type': 'notification_event',
             'name': event_name,
             'data': data})
    except Exception as e:
        # channel fails shouldn't crash the calling process
        logger.exception(e)


def send_notification(user_pk, message, id=None, level='info', links=None):
    channel_layer = get_channel_layer()
    try:
        async_to_sync(channel_layer.group_send)(
            get_group_name(user_pk),
            {'type': 'notification_message',
             'id': id,
             'level': level,
             'text': message,
             'links': links or []})
    except Exception as e:
        # channel fails shouldn't crash the calling process
        logger.exception(e)


def can_join_room(user, object_cls, object_pk):
    if object_cls != 'document':
        return False
    try:
        object_pk = int(object_pk)
    except (TypeError, ValueError):
        return False
    from core.models import Document  # core.models imports this module
    return Document.objects.for_user(user).filter(pk=object_pk).exists()


class NotificationConsumer(WebsocketConsumer):
    def connect(self):
        self.room = None
        if self.scope['user'].is_authenticated:
            async_to_sync(self.channel_layer.group_add)(
                get_group_name(self.scope['user'].pk),
                self.channel_name)
            self.accept()

    def disconnect(self, close_code):
        if self.scope['user'].is_authenticated:
            async_to_sync(self.channel_layer.group_discard)(
                get_group_name(self.scope['user'].pk),
                self.channel_name)
            if self.room:
                async_to_sync(self.channel_layer.group_discard)(
                    self.room,
                    self.channel_name)

    def receive(self, text_data):
        msg = json.loads(text_data)
        if 'type' in msg:
            if msg['type'] == 'notif' and self.scope['user'].is_superuser:  # DEBUG notifs
                send_notification(msg['user_pk'], msg['text'], level=getattr(msg, 'level', 'info'))
            elif msg['type'] == 'join-room':
                self.join_room(msg.get('object_cls'), msg.get('object_pk'))

    def join_room(self, object_cls, object_pk):
        # Rooms carry the events of a single object, only let in users who can access it.
        if not self.scope['user'].is_authenticated or not can_join_room(self.scope['user'], object_cls, object_pk):
            logger.warning('User %s was refused access to room %s-%s',
                           self.scope['user'].pk, object_cls, object_pk)
            return
        room = get_room_name(object_cls, int(object_pk))
        if self.room and self.room != room:
            async_to_sync(self.channel_layer.group_discard)(
                self.room,
                self.channel_name)
        self.room = room
        async_to_sync(self.channel_layer.group_add)(
            self.room,
            self.channel_name)

    def notification_message(self, event):
        self.send(json.dumps({'type': 'message',
                              'id': event['id'],
                              'level': event['level'],
                              'text': event['text'],
                              'links': event['links']}))

    def notification_event(self, event):
        self.send(json.dumps({'type': 'event',
                              'name': event['name'],
                              'data': event['data']}))
