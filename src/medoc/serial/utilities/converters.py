def to_u_int_16_ex(array, start_index) -> int:
    if len(array) <= start_index:
        raise IndexError(f'Index out of range {start_index}')
    b = array[start_index]
    copy = list(array[0:start_index])
    copy.append(array[start_index + 1])
    copy.append(b)
    if len(array[start_index + 2:]) != 0:
        copy.append(array[start_index + 2:])
    r = copy[start_index:start_index + 2]
    return int.from_bytes(r, byteorder='little')


def to_int_16(array, start_index):
    if len(array) <= start_index:
        raise IndexError(f'Index out of range {start_index}')
    b = array[start_index]
    copy = list(array[0:start_index])
    copy.append(array[start_index + 1])
    copy.append(b)
    if len(array[start_index + 2:]) != 0:
        copy.append(array[start_index + 2:])
    r = copy[start_index:start_index + 2]
    return int.from_bytes(r, byteorder='little', signed=True)


def to_uint_16(array, start_index):
    if len(array) <= start_index:
        raise IndexError(f'Index out of range {start_index}')
    b = array[start_index]
    copy = list(array[0:start_index])
    copy.append(array[start_index + 1])
    copy.append(b)
    if len(array[start_index + 2:]) != 0:
        copy.append(array[start_index + 2:])
    r = copy[start_index:start_index + 2]
    return int.from_bytes(r, byteorder='little', signed=False)


def to_uint_32(array, start_index):
    if len(array) < start_index + 4:
        raise IndexError(f'Index out of range {start_index}')
    copy = list(array[0:start_index])
    reversed_slice = array[start_index: start_index + 4]
    copy.extend(reversed_slice[::-1])
    trail = array[start_index + 4:]
    copy.extend(trail)
    r = copy[start_index:start_index + 4]
    return int.from_bytes(r, byteorder='little', signed=False)


def to_string(array, start_index):
    length = array[start_index]
    if length > 0:
        a = bytes(array[start_index + 1:start_index + 1 + length])
        return str(a, 'utf-8')
    return ''


def get_bytes16(short, border='little'):
    return short.to_bytes(2, byteorder=border)


def get_bytes32(integer):
    return integer.to_bytes(4, byteorder='little')


def set_bit(v, index, x) -> int:
    mask = 1 << index
    v &= ~mask
    if x:
        v |= mask
    return v


def get_bit(v, index) -> bool:
    return bool(v & (1 << index))
