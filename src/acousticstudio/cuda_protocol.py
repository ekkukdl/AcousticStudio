"""Bounded binary messages on private parent/child pipes (never a network API)."""
import pickle
import struct

MAX_MESSAGE_BYTES = 64 * 1024 * 1024


def _read_exact(stream, length):
    output = bytearray()
    while len(output) < length:
        chunk = stream.read(length - len(output))
        if not chunk:
            raise EOFError('CUDA 계산 프로세스의 연결이 종료되었습니다.')
        output.extend(chunk)
    return bytes(output)


def read_message(stream):
    size, = struct.unpack('!I', _read_exact(stream, 4))
    if not 0 < size <= MAX_MESSAGE_BYTES:
        raise ValueError('CUDA 계산 메시지 크기가 허용 범위를 벗어났습니다.')
    # Both ends are our own subprocess; no external/user-supplied pickle is read.
    return pickle.loads(_read_exact(stream, size))


def write_message(stream, value):
    data = pickle.dumps(value, protocol=5)
    if len(data) > MAX_MESSAGE_BYTES:
        raise ValueError('CUDA 계산 메시지가 너무 큽니다.')
    stream.write(struct.pack('!I', len(data)))
    stream.write(data)
    stream.flush()
