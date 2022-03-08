import struct
import numpy as np


def to_redis(red, array, name):
    """
    Store given Numpy array 'a' in Redis under key 'n'
    """
    h, w = array.shape[:2]
    shape = struct.pack('>II', h, w)
    encoded = shape + array.tobytes()

    # Store encoded data in Redis
    red.set(name, encoded)
    return


def from_redis(red, name):
    """
    Retrieve Numpy array from Redis key 'n'
    """
    encoded = red.get(name)
    h, w = struct.unpack('>II', encoded[:8])
    array = np.frombuffer(encoded, dtype=np.uint8, offset=8).reshape(h, w, 3)
    return array
