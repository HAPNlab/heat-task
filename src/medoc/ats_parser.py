"""Parser for Medoc MMS .ats experiment files (MS-NRBF binary format).

.ats files are Pathway/ATS container files embedding multiple NRBF streams,
each serialized with .NET BinaryFormatter. This module finds the ThermodeProgram
streams and extracts the experiment data from them.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

from medoc.experiment import Experiment, RampAndHoldSequence, ThermodeProgram

# NRBF record type bytes
_RT_STREAM_HEADER = 0x00
_RT_CLASS_WITH_ID = 0x01                        # lightweight: objectId + metadataId
_RT_SYSTEM_CLASS_WITH_MEMBERS_AND_TYPES = 0x04  # mscorlib class, no LibraryId
_RT_CLASS_WITH_MEMBERS_AND_TYPES = 0x05         # external class + LibraryId
_RT_BINARY_OBJECT_STRING = 0x06
_RT_BINARY_ARRAY = 0x07
_RT_MEMBER_PRIMITIVE_TYPED = 0x08
_RT_MEMBER_REFERENCE = 0x09
_RT_OBJECT_NULL = 0x0A
_RT_MESSAGE_END = 0x0B
_RT_BINARY_LIBRARY = 0x0C
_RT_OBJECT_NULL_MULTIPLE_256 = 0x0D
_RT_OBJECT_NULL_MULTIPLE = 0x0E
_RT_ARRAY_SINGLE_PRIMITIVE = 0x0F
_RT_ARRAY_SINGLE_OBJECT = 0x10
_RT_ARRAY_SINGLE_STRING = 0x11

# BinaryTypeEnum constants
_BT_PRIMITIVE = 0
_BT_STRING = 1
_BT_OBJECT = 2
_BT_SYSTEM_CLASS = 3
_BT_CLASS = 4
_BT_OBJECT_ARRAY = 5
_BT_STRING_ARRAY = 6
_BT_PRIMITIVE_ARRAY = 7

# PrimitiveTypeEnum -> (struct format, byte size)
_PRIM: dict[int, tuple[str, int]] = {
    1:  ('?', 1),    # Boolean
    2:  ('B', 1),    # Byte
    3:  ('<H', 2),   # Char (UTF-16 LE)
    6:  ('<d', 8),   # Double
    7:  ('<h', 2),   # Int16
    8:  ('<i', 4),   # Int32
    9:  ('<q', 8),   # Int64
    10: ('b', 1),    # SByte
    11: ('<f', 4),   # Single
    12: ('<q', 8),   # TimeSpan (Int64 ticks)
    13: ('<Q', 8),   # DateTime (UInt64 ticks)
    14: ('<H', 2),   # UInt16
    15: ('<I', 4),   # UInt32
    16: ('<Q', 8),   # UInt64
}

# Marker to signal "N nulls" from null-multiple records (only valid inside arrays)
class _NullRun:
    __slots__ = ('count',)
    def __init__(self, count: int) -> None:
        self.count = count


# Placeholder for a forward reference (object defined later in the stream)
class _Ref:
    __slots__ = ('id_ref',)
    def __init__(self, id_ref: int) -> None:
        self.id_ref = id_ref


class _NrbfStream:
    """Parse one NRBF stream and expose its object graph."""

    def __init__(self, data: bytes, start: int) -> None:
        self._d = data
        self._p = start
        self._objects: dict[int, Any] = {}
        self._class_defs: dict[int, dict] = {}  # objectId -> class_def

    # ------------------------------------------------------------------
    # Low-level readers
    # ------------------------------------------------------------------

    def _u8(self) -> int:
        v = self._d[self._p]; self._p += 1; return v

    def _i32(self) -> int:
        v = struct.unpack_from('<i', self._d, self._p)[0]; self._p += 4; return v

    def _lps(self) -> str:
        """7-bit length-prefixed UTF-8 string."""
        length = shift = 0
        for _ in range(5):
            b = self._d[self._p]; self._p += 1
            length |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7
        s = self._d[self._p:self._p + length].decode('utf-8', errors='replace')
        self._p += length
        return s

    def _prim(self, ptype: int) -> Any:
        fmt, sz = _PRIM[ptype]
        v = struct.unpack_from(fmt, self._d, self._p)[0]
        self._p += sz
        return v

    # ------------------------------------------------------------------
    # Record dispatch
    # ------------------------------------------------------------------

    def _next(self) -> Any:
        """Read and dispatch the next record, returning its value."""
        rt = self._u8()
        return self._dispatch(rt)

    def _dispatch(self, rt: int) -> Any:
        if rt == _RT_BINARY_LIBRARY:
            return self._r_binary_library()
        if rt == _RT_CLASS_WITH_MEMBERS_AND_TYPES:
            return self._r_class_full(system=False)
        if rt == _RT_SYSTEM_CLASS_WITH_MEMBERS_AND_TYPES:
            return self._r_class_full(system=True)
        if rt == _RT_CLASS_WITH_ID:
            return self._r_class_with_id()
        if rt == _RT_BINARY_OBJECT_STRING:
            return self._r_string()
        if rt == _RT_MEMBER_REFERENCE:
            return self._r_ref()
        if rt == _RT_OBJECT_NULL:
            return None
        if rt == _RT_OBJECT_NULL_MULTIPLE_256:
            return _NullRun(self._u8())
        if rt == _RT_OBJECT_NULL_MULTIPLE:
            return _NullRun(self._i32())
        if rt == _RT_ARRAY_SINGLE_OBJECT:
            return self._r_array_single_object()
        if rt == _RT_ARRAY_SINGLE_PRIMITIVE:
            return self._r_array_single_primitive()
        if rt == _RT_ARRAY_SINGLE_STRING:
            return self._r_array_single_string()
        if rt == _RT_BINARY_ARRAY:
            return self._r_binary_array()
        if rt == _RT_MEMBER_PRIMITIVE_TYPED:
            ptype = self._u8()
            return self._prim(ptype)
        raise ValueError(f"Unhandled record type 0x{rt:02x} at 0x{self._p - 1:x}")

    # ------------------------------------------------------------------
    # Record handlers
    # ------------------------------------------------------------------

    def _r_binary_library(self) -> None:
        self._i32()   # libraryId
        self._lps()   # name

    def _r_class_full(self, system: bool) -> dict:
        obj_id = self._i32()
        class_name = self._lps()
        member_count = self._i32()
        member_names = [self._lps() for _ in range(member_count)]
        type_infos = self._read_member_type_info(member_count)
        if not system:
            self._i32()  # LibraryId (not needed)

        class_def = {
            'class_name': class_name,
            'member_names': member_names,
            'type_infos': type_infos,
        }
        self._class_defs[obj_id] = class_def

        values = self._read_member_values(type_infos)
        obj = {'__class__': class_name, **dict(zip(member_names, values))}
        self._objects[obj_id] = obj
        return obj

    def _r_class_with_id(self) -> dict:
        obj_id = self._i32()
        metadata_id = self._i32()
        class_def = self._class_defs[metadata_id]
        values = self._read_member_values(class_def['type_infos'])
        obj = {'__class__': class_def['class_name'], **dict(zip(class_def['member_names'], values))}
        self._objects[obj_id] = obj
        return obj

    def _r_string(self) -> str:
        obj_id = self._i32()
        value = self._lps()
        self._objects[obj_id] = value
        return value

    def _r_ref(self) -> Any:
        id_ref = self._i32()
        if id_ref in self._objects:
            return self._objects[id_ref]
        return _Ref(id_ref)

    def _r_array_single_object(self) -> list:
        obj_id = self._i32()
        length = self._i32()
        items: list = []
        while len(items) < length:
            val = self._next()
            if isinstance(val, _NullRun):
                items.extend([None] * val.count)
            else:
                items.append(val)
        self._objects[obj_id] = items
        return items

    def _r_array_single_primitive(self) -> list:
        obj_id = self._i32()
        length = self._i32()
        ptype = self._u8()
        fmt, sz = _PRIM[ptype]
        items = [
            struct.unpack_from(fmt, self._d, self._p + i * sz)[0]
            for i in range(length)
        ]
        self._p += length * sz
        self._objects[obj_id] = items
        return items

    def _r_array_single_string(self) -> list:
        obj_id = self._i32()
        length = self._i32()
        items = [self._next() for _ in range(length)]
        self._objects[obj_id] = items
        return items

    def _r_binary_array(self) -> list:
        obj_id = self._i32()
        array_type = self._u8()
        rank = self._i32()
        lengths = [self._i32() for _ in range(rank)]
        if array_type >= 3:  # offset arrays include lower bounds
            for _ in range(rank):
                self._i32()
        bt = self._u8()
        if bt == _BT_PRIMITIVE:
            extra = self._u8()
        elif bt == _BT_SYSTEM_CLASS:
            extra = self._lps()
        elif bt == _BT_CLASS:
            extra = self._lps(); self._i32()
        elif bt == _BT_PRIMITIVE_ARRAY:
            extra = self._u8()
        else:
            extra = None

        total = 1
        for ln in lengths:
            total *= ln

        items: list = []
        while len(items) < total:
            if bt == _BT_PRIMITIVE:
                items.append(self._prim(extra))
            else:
                val = self._next()
                if isinstance(val, _NullRun):
                    items.extend([None] * val.count)
                else:
                    items.append(val)

        self._objects[obj_id] = items
        return items

    # ------------------------------------------------------------------
    # Type info and member value readers
    # ------------------------------------------------------------------

    def _read_member_type_info(self, count: int) -> list[tuple[int, Any]]:
        binary_types = [self._u8() for _ in range(count)]
        type_infos = []
        for bt in binary_types:
            if bt == _BT_PRIMITIVE:
                extra = self._u8()
            elif bt == _BT_SYSTEM_CLASS:
                extra = self._lps()
            elif bt == _BT_CLASS:
                extra = self._lps(); self._i32()  # class name + libraryId
            elif bt == _BT_PRIMITIVE_ARRAY:
                extra = self._u8()
            else:
                extra = None
            type_infos.append((bt, extra))
        return type_infos

    def _read_member_values(self, type_infos: list[tuple[int, Any]]) -> list[Any]:
        values = []
        for bt, extra in type_infos:
            if bt == _BT_PRIMITIVE:
                values.append(self._prim(extra))
            else:
                val = self._next()
                # Null-runs are only valid inside arrays; treat as None in member context
                if isinstance(val, _NullRun):
                    val = None
                values.append(val)
        return values

    # ------------------------------------------------------------------
    # Forward reference resolution
    # ------------------------------------------------------------------

    def _resolve(self, obj: Any, seen: set | None = None) -> Any:
        """Recursively resolve all _Ref placeholders after the stream is fully parsed."""
        if seen is None:
            seen = set()
        if isinstance(obj, _Ref):
            resolved = self._objects.get(obj.id_ref)
            return self._resolve(resolved, seen)
        if isinstance(obj, dict):
            oid = id(obj)
            if oid in seen:
                return obj
            seen.add(oid)
            for k, v in obj.items():
                if isinstance(v, (_Ref, dict, list)):
                    obj[k] = self._resolve(v, seen)
        elif isinstance(obj, list):
            oid = id(obj)
            if oid in seen:
                return obj
            seen.add(oid)
            for i, v in enumerate(obj):
                if isinstance(v, (_Ref, dict, list)):
                    obj[i] = self._resolve(v, seen)
        return obj

    # ------------------------------------------------------------------
    # Stream-level parse
    # ------------------------------------------------------------------

    def parse(self) -> Any:
        """Parse the stream and return the root object (objectId=1)."""
        assert self._d[self._p] == _RT_STREAM_HEADER, \
            f"Expected stream header at 0x{self._p:x}, got 0x{self._d[self._p]:02x}"
        root_id = struct.unpack_from('<i', self._d, self._p + 1)[0]
        self._p += 17  # SerializedStreamHeader is 17 bytes

        while True:
            rt = self._u8()
            if rt == _RT_MESSAGE_END:
                break
            self._dispatch(rt)

        # Resolve forward references now that the whole stream is parsed
        for obj in list(self._objects.values()):
            self._resolve(obj)

        return self._objects.get(root_id)


# ---------------------------------------------------------------------------
# Locate NRBF streams within the .ats container
# ---------------------------------------------------------------------------

_STREAM_MAGIC = bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF,
                        0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])


def _find_thermode_program_streams(data: bytes) -> list[int]:
    """Return byte offsets of each embedded NRBF stream that contains a ThermodeProgram."""
    offsets = []
    search = b'Medoc.ATS.ThermodeProgram'
    pos = 0
    while True:
        idx = data.find(search, pos)
        if idx == -1:
            break
        # Walk backwards to find the NRBF stream header (0x00 + magic) that precedes this class
        stream_start = data.rfind(_STREAM_MAGIC, 0, idx)
        if stream_start != -1 and stream_start not in offsets:
            offsets.append(stream_start)
        pos = idx + 1
    return sorted(offsets)


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _as_float(v: Any) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):
        return float(v.get('value__', 0))
    return 0.0


def _as_int(v: Any) -> int:
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, dict):
        return int(v.get('value__', 0))
    return 0


def _has_time_mark(event_spec: Any) -> bool:
    """True if this event spec is a time-based event with a non-zero TTL code."""
    if not isinstance(event_spec, dict):
        return False
    ttl = event_spec.get('TTLEventType', {})
    if not isinstance(ttl, dict) or ttl.get('value__', 0) == 0:
        return False
    condition = event_spec.get('m_condition', {})
    # Temperature-condition events need condition-event serialisation we don't support yet
    return isinstance(condition, dict) and 'TemperatureConditionSpec' not in condition.get('__class__', '')


def _extract_sequences(sequences_field: Any) -> tuple[RampAndHoldSequence, ...]:
    """Extract RampAndHoldSequence objects from the m_sequences ArrayList."""
    if not isinstance(sequences_field, dict):
        return ()

    items: list = sequences_field.get('_items', []) or []
    size: int = sequences_field.get('_size', len(items))
    if not isinstance(size, int):
        size = _as_int(size)

    seqs = []
    for item in items[:size]:
        if not isinstance(item, dict):
            continue
        if 'Medoc.ATS.RampAndHoldSequence' not in item.get('__class__', ''):
            continue

        def _enum_val(raw: Any, default: int = 0) -> int:
            if isinstance(raw, (int, float)):
                return int(raw)
            if isinstance(raw, dict):
                return _as_int(raw.get('value__', default))
            return default

        seqs.append(RampAndHoldSequence(
            number=_as_int(item.get('m_number')),
            trials=_as_int(item.get('m_trialsNumber')) or 1,
            baseline_temp=_as_float(item.get('m_baselineTemp')),
            destination_temp=_as_float(item.get('m_destinationTemp')),
            destination_rate=_as_float(item.get('m_destinationRate')),
            return_rate=_as_float(item.get('m_returnRate')),
            duration_ms=_as_int(item.get('m_durationTime')),
            time_before_ms=_as_int(item.get('m_timeBeforeSequence')),
            waiting_time_for_response_ms=_as_int(item.get('m_waitingTimeForResponse')),
            inter_trials_min_ms=_as_int(item.get('m_interTrialsTimeMin')),
            inter_trials_max_ms=_as_int(item.get('m_interTrialsTimeMax')),
            inter_trials_time_option=_enum_val(item.get('m_interTrialsTimeOption'), default=1),
            destination_criterion=_enum_val(item.get('m_destinationCriterion'), default=0),
            trigger=_enum_val(item.get('m_trigger'), default=0),
            randomize_with_next=bool(item.get('m_isRandomizeWithNext', False)),
            mark_onset=_has_time_mark(item.get('m_onsetEvent')),
            mark_destination=_has_time_mark(item.get('m_destinationEvent')),
            mark_end_of_duration=_has_time_mark(item.get('m_endOfDurationEvent')),
            mark_end_of_trial=_has_time_mark(item.get('m_endOfTrialEvent')),
        ))
    return tuple(seqs)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_ats(path: str | Path) -> Experiment:
    """Parse a Medoc MMS .ats file and return an Experiment.

    Raises ValueError if no ThermodeProgram streams are found.
    """
    data = Path(path).read_bytes()
    stream_offsets = _find_thermode_program_streams(data)
    if not stream_offsets:
        raise ValueError(f"No ThermodeProgram streams found in {path}")

    programs = []
    for offset in stream_offsets:
        try:
            root = _NrbfStream(data, offset).parse()
        except Exception as exc:
            raise ValueError(f"Failed to parse NRBF stream at 0x{offset:x} in {path}") from exc

        if not isinstance(root, dict):
            continue

        name = root.get('m_name', '')
        if not isinstance(name, str):
            name = str(name)

        sequences = _extract_sequences(root.get('m_sequences'))
        programs.append(ThermodeProgram(
            name=name,
            sequences=sequences,
            randomize_sequences=bool(root.get('m_randomizeSequences;', False)),
            delay_before_ms=_as_int(root.get('m_delayBeforProgram', 0)),
        ))

    return Experiment(programs=tuple(programs))
