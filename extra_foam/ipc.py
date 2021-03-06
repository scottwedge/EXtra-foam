"""
Distributed under the terms of the BSD 3-Clause License.

The full license is in the file LICENSE, distributed with this software.

Author: Jun Zhu <jun.zhu@xfel.eu>
Copyright (C) European X-Ray Free-Electron Laser Facility GmbH.
All rights reserved.
"""
import weakref

import json
import numpy as np

import redis

from .config import config
from .serialization import deserialize_image, serialize_image
from .file_io import read_cal_constants


class _RedisQueueBase:
    def __init__(self, namespace, **kwargs):
        self._key = namespace
        self._redis = redis.Redis(**kwargs)


class RQProducer(_RedisQueueBase):
    def __init__(self, namespace):
        super().__init__(namespace)

    def put(self, key, value):
        """Put item into the queue."""
        self._redis.rpush(self._key, json.dumps({key: value}))


class RQConsumer(_RedisQueueBase):
    def __init__(self, namespace):
        super().__init__(namespace)

    def get(self, block=True, timeout=None):
        if block:
            item = self._redis.blpop(self._key, timeout=timeout)
        else:
            item = self._redis.lpop(self._key)

        if item:
            return json.loads(item, encoding='utf8')

    def get_nowait(self):
        return self.get(False)

    def get_all(self):
        msg = dict()
        while True:
            new_msg = self.get_nowait()
            if new_msg is None:
                break
            msg.update(new_msg)

        return msg


_GLOBAL_REDIS_CONNECTION = None
_GLOBAL_REDIS_CONNECTION_BYTES = None


# keep tracking lazily created connections
_global_connections = dict()


def init_redis_connection(host, port, *, password=None):
    """Initialize Redis client connection.

    :param str host: IP address of the Redis server.
    :param int port:: Port of the Redis server.
    :param str password: password for the Redis server.

    :return: Redis connection.
    """
    # reset all connections first
    global _GLOBAL_REDIS_CONNECTION
    _GLOBAL_REDIS_CONNECTION = None
    global _GLOBAL_REDIS_CONNECTION_BYTES
    _GLOBAL_REDIS_CONNECTION_BYTES = None

    for connections in _global_connections.values():
        for ref in connections:
            c = ref()
            if c is not None:
                c.reset()

    # initialize new connection
    if config["REDIS_UNIX_DOMAIN_SOCKET_PATH"]:
        raise NotImplementedError(
            "Unix domain socket connection is not supported!")
        # connection = redis.Redis(
        #     unix_socket_path=config["REDIS_UNIX_DOMAIN_SOCKET_PATH"],
        #     decode_responses=decode_responses
        # )
    else:
        # the following two must have different pools
        connection = redis.Redis(
            host, port, password=password, decode_responses=True)
        connection_byte = redis.Redis(
            host, port, password=password, decode_responses=False)

    _GLOBAL_REDIS_CONNECTION = connection
    _GLOBAL_REDIS_CONNECTION_BYTES = connection_byte
    return connection


def redis_connection(decode_responses=True):
    """Return a Redis connection."""
    if decode_responses:
        return _GLOBAL_REDIS_CONNECTION
    return _GLOBAL_REDIS_CONNECTION_BYTES


class MetaRedisConnection(type):
    def __call__(cls, *args, **kw):
        instance = super().__call__(*args, **kw)
        name = cls.__name__
        if name not in _global_connections:
            _global_connections[name] = []
        _global_connections[name].append(weakref.ref(instance))
        return instance


class RedisConnection(metaclass=MetaRedisConnection):
    """Lazily evaluated Redis connection on access."""
    def __init__(self, decode_responses=True):
        self._db = None
        self._decode_responses = decode_responses

    def __get__(self, instance, instance_type):
        if self._db is None:
            self._db = redis_connection(
                decode_responses=self._decode_responses)
        return self._db

    def reset(self):
        self._db = None


class RedisSubscriber(metaclass=MetaRedisConnection):
    """Lazily evaluated Redis subscriber."""
    def __init__(self, channel, decode_responses=True):
        self._sub = None
        self._decode_responses = decode_responses
        self._channel = channel

    def __get__(self, instance, instance_type):
        if self._sub is None:
            self._sub = redis_connection(
                decode_responses=self._decode_responses).pubsub(
                ignore_subscribe_messages=True)
            try:
                self._sub.subscribe(self._channel)
            except redis.ConnectionError:
                self._sub = None

        return self._sub

    def reset(self):
        if self._sub is not None:
            self._sub.close()
        self._sub = None


class RedisPSubscriber(metaclass=MetaRedisConnection):
    """Lazily evaluated Redis psubscriber."""
    def __init__(self, pattern, decode_responses=True):
        self._sub = None
        self._decode_responses = decode_responses
        self._pattern = pattern

    def __get__(self, instance, instance_type):
        if self._sub is None:
            self._sub = redis_connection(
                decode_responses=self._decode_responses).pubsub(
                ignore_subscribe_messages=True)
            try:
                self._sub.psubscribe(self._pattern)
            except redis.ConnectionError:
                self._sub = None

        return self._sub

    def reset(self):
        if self._sub is not None:
            self._sub.close()
        self._sub = None


class ProcessLogger:
    """Worker which publishes log message in another Process.

    Note: remember to change other part of the code if the log pattern
    changes.
    """

    _db = RedisConnection()

    def debug(self, msg):
        self._db.publish("log:debug", msg)

    def info(self, msg):
        self._db.publish("log:info", msg)

    def warning(self, msg):
        self._db.publish("log:warning", msg)

    def error(self, msg):
        self._db.publish("log:error", msg)


process_logger = ProcessLogger()


class ReferencePub:
    _db = RedisConnection()

    def set(self, image):
        """Publish the reference image in Redis."""
        self._db.publish("reference_image", serialize_image(image))

    def remove(self):
        """Notify to remove the current reference image."""
        self._db.publish("reference_image", '')


class ReferenceSub:
    _sub = RedisSubscriber("reference_image", decode_responses=False)

    def update(self, ref):
        """Parse all reference image operations.

        :return numpy.ndarray: the updated reference image.
        """
        sub = self._sub
        while True:
            msg = sub.get_message(ignore_subscribe_messages=True)
            if msg is None:
                break

            v = msg['data']
            if not v:
                ref = None
            else:
                ref = deserialize_image(v)
        return ref


class ImageMaskPub:
    _db = RedisConnection()

    def add(self, mask_region):
        """Add a region to the current mask."""
        self._db.publish("image_mask", 'add')
        self._db.publish("image_mask", str(mask_region))

    def erase(self, mask_region):
        """Erase a region from the current mask."""
        self._db.publish("image_mask", 'erase')
        self._db.publish("image_mask", str(mask_region))

    def set(self, mask):
        """Set the whole mask."""
        self._db.publish("image_mask", 'set')
        self._db.publish("image_mask",
                         serialize_image(mask, is_mask=True))

    def remove(self):
        """Completely remove all the mask."""
        self._db.publish("image_mask", 'remove')


class ImageMaskSub:
    _sub = RedisSubscriber("image_mask", decode_responses=False)

    def update(self, mask, shape):
        """Parse all masking operations.

        :param numpy.ndarray mask: image mask. dtype = np.bool.
        :param tuple/list shape: shape of the image.

        :return numpy.ndarray: the updated mask.
        """
        sub = self._sub
        if sub is None:
            return mask

        # process all messages related to mask
        while True:
            msg = sub.get_message(ignore_subscribe_messages=True)
            if msg is None:
                break

            action = msg['data']
            if action == b'set':
                mask = deserialize_image(sub.get_message()['data'], is_mask=True)
            elif action in [b'add', b'erase']:
                if mask is None:
                    mask = np.zeros(shape, dtype=np.bool)

                data = sub.get_message()['data'].decode("utf-8")
                x, y, w, h = [int(v) for v in data[1:-1].split(',')]
                if action == b'add':
                    mask[y:y+h, x:x+w] = True
                else:
                    mask[y:y+h, x:x+w] = False
            else:  # data == 'remove'
                mask = None

        return mask


class CalConstantsPub:
    _db = RedisConnection()

    def set_gain(self, filepath):
        """Publish the gain constants filepath in Redis.

        ：param str filepath: path of the gain constants file.
        """
        self._db.publish("cal_constants:gain", filepath)

    def remove_gain(self):
        """Notify to remove the current gain constants."""
        self._db.publish("cal_constants:gain", '')

    def set_offset(self, filepath):
        """Publish the offset constants filepath in Redis.

        ：param str filepath: path of the offset constants file.
        """
        self._db.publish("cal_constants:offset", filepath)

    def remove_offset(self):
        """Notify to remove the current offset constants."""
        self._db.publish("cal_constants:offset", '')


class CalConstantsSub:
    _sub = RedisPSubscriber("cal_constants:*")

    def update(self, gain, offset):
        """Parse all cal constants operations."""
        sub = self._sub
        new_gain = False
        gain_fp = None
        new_offset = False
        offset_fp = None
        while True:
            msg = sub.get_message(ignore_subscribe_messages=True)
            if msg is None:
                break

            c = msg['channel'].split(":")[-1]
            v = msg['data']
            if c == 'gain':
                if not v:
                    gain = None
                    new_gain = True
                else:
                    gain_fp = v
            elif c == 'offset':
                if not v:
                    offset = None
                    new_offset = True
                else:
                    offset_fp = v

        if gain_fp is not None:
            gain = read_cal_constants(gain_fp)
            new_gain = True
        if offset_fp is not None:
            offset = read_cal_constants(offset_fp)
            new_offset = True

        return new_gain, gain, new_offset, offset
