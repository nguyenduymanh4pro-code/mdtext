from typing import List, Tuple

def string_insert(orig: bytes, ins: bytes, index: int) -> bytes:
    return orig[:index] + ins + orig[index:]

def insert_braces(effect_text: str, parts_arr: List[Tuple[int,int]]) -> str:
    parts_arr = [(a,b) for (a,b) in parts_arr if isinstance(a, int) and isinstance(b, int) and a < b]
    if not parts_arr:
        return effect_text
    ans = effect_text.encode('utf-8')
    insertion_dict = {}
    for (a, b) in parts_arr:
        left_index = a
        right_index = b + 1
        if left_index not in insertion_dict:
            insertion_dict[left_index] = {'L': 0, 'R': 0}
        if right_index not in insertion_dict:
            insertion_dict[right_index] = {'L': 0, 'R': 0}
        insertion_dict[left_index]['L'] += 1
        insertion_dict[right_index]['R'] += 1
    for index in sorted(insertion_dict.keys(), reverse=True):
        ins = b''
        ins += b'}' * insertion_dict[index]['R']
        ins += b'{' * insertion_dict[index]['L']
        ans = string_insert(ans, ins, index)
    try:
        return ans.decode('utf-8')
    except Exception:
        return ans.decode('utf-8', errors='replace')

def count_top_level_braces(text: str) -> int:
    depth = 0
    top_level_count = 0
    for c in text:
        if c == '{':
            if depth == 0:
                top_level_count += 1
            depth += 1
        elif c == '}':
            if depth > 0:
                depth -= 1
    return top_level_count