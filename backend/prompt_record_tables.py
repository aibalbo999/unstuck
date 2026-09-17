"""Lossless record-table encoding for repetitive prompt JSON field names."""

import json

TABLE_RULE = (
    'JSON 的 __record_table__=1 表示無損資料表：columns 是欄名，rows 每列依欄名順序對應值；'
    '有 row_keys 時代表以該鍵索引的物件，否則代表原陣列。absent 以零起算列號字串列出缺少欄位的零起算索引；展開時移除這些欄位，其餘 null 仍保留。巢狀表依相同規則展開。'
    'null、false、0 含義不同；引用資料時使用展開後的原欄位路徑、日期與單位，不得把欄位錯配。'
)


def _size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False))


def _validate_table(table):
    """Reject ambiguous source markers instead of discarding unrecognized data."""
    if (type(table.get('__record_table__')) is not int or table['__record_table__'] != 1
            or not {'columns', 'rows'} <= set(table)
            or set(table) - {'__record_table__', 'columns', 'rows', 'row_keys', 'absent'}):
        raise ValueError('ambiguous record table')
    columns, rows = table['columns'], table['rows']
    if (not isinstance(columns, list) or not columns or not all(isinstance(k, str) for k in columns)
            or len(set(columns)) != len(columns) or '__record_table__' in columns
            or not isinstance(rows, list)
            or any(not isinstance(row, list) or len(row) != len(columns) for row in rows)):
        raise ValueError('invalid record table dimensions')
    if 'row_keys' in table:
        keys = table['row_keys']
        if (not isinstance(keys, list) or len(keys) != len(rows)
                or not all(isinstance(k, str) for k in keys) or len(set(keys)) != len(keys)):
            raise ValueError('invalid record table keys')
    absent = table.get('absent', {})
    if not isinstance(absent, dict):
        raise ValueError('invalid absent cells')
    for row_key, indexes in absent.items():
        if (not isinstance(row_key, str) or not row_key.isascii() or not row_key.isdecimal()
                or str(int(row_key)) != row_key or int(row_key) >= len(rows)
                or not isinstance(indexes, list)
                or any(type(i) is not int or not 0 <= i < len(columns) for i in indexes)
                or len(set(indexes)) != len(indexes)
                or any(rows[int(row_key)][i] is not None for i in indexes)):
            raise ValueError('invalid absent cell address or value')


def unpack_record_tables(value, *, strict=False):
    """Expand our representation, retaining missing versus explicit null cells."""
    if isinstance(value, list):
        return [unpack_record_tables(item, strict=strict) for item in value]
    if not isinstance(value, dict):
        return value
    if value.get('__record_table__') == 1:
        if strict:
            _validate_table(value)
        rows = []
        for i, values in enumerate(value['rows']):
            absent = value.get('absent', {}).get(str(i), [])
            rows.append({key: unpack_record_tables(item, strict=strict)
                         for j, (key, item) in enumerate(zip(value['columns'], values)) if j not in absent})
        return dict(zip(value['row_keys'], rows)) if 'row_keys' in value else rows
    return {key: unpack_record_tables(item, strict=strict) for key, item in value.items()}


def pack_record_tables(value):
    """Keep every key/value and ordering; compatible optional fields use absent indexes."""
    if isinstance(value, list):
        packed = [pack_record_tables(item) for item in value]
        records, row_keys = packed, None
    elif isinstance(value, dict):
        packed = {key: pack_record_tables(item) for key, item in value.items()}
        records, row_keys = list(packed.values()), list(packed)
        if '__record_table__' in value or not all(isinstance(key, str) for key in value):
            return packed
    else:
        return value
    if len(records) < 3 or not all(isinstance(record, dict) and record for record in records):
        return packed
    # A superset schema may contain optional fields. Preserve original key order
    # and distinguish absent fields from present null/false/zero values.
    columns = list(max(records, key=len))
    if (not all(isinstance(key, str) for key in columns)
            or '__record_table__' in columns
            or any(list(record) != [key for key in columns if key in record]
                   for record in records)):
        return packed
    table = {'__record_table__': 1, 'columns': columns,
             'rows': [[record.get(key) for key in columns] for record in records]}
    absent = {str(i): [j for j, key in enumerate(columns) if key not in record]
              for i, record in enumerate(records) if len(record) != len(columns)}
    if absent:
        table['absent'] = absent
    if row_keys is not None:
        table['row_keys'] = row_keys
    return table if _size(table) + 64 < _size(packed) else packed
