"""Lossless record-table encoding for repetitive prompt JSON field names."""

import json

TABLE_RULE = (
    'JSON 的 __record_table__=1 表示無損資料表：columns 是欄名，rows 每列依欄名順序對應值；'
    '有 row_keys 時代表以該鍵索引的物件，否則代表原陣列。absent 以零起算列號字串列出缺少欄位的零起算索引；展開時移除這些欄位，其餘 null 仍保留。巢狀表依相同規則展開。'
    'null、false、0 含義不同；引用資料時使用展開後的原欄位路徑、日期與單位，不得把欄位錯配。'
)


def _size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False))


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
