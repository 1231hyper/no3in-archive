"""Database line decoder (vendored from r7_census_laws.py, verbatim).

Format (Flammenkamp, page revision 2026-08-19): each line is a
symmetry-class character from ". : / - o c x + *" (iden rot2 dia1 ort1
rot4 rct4 dia2 ort2 full) followed by the occupied columns, two per row,
top to bottom, encoded in the 90-character column alphabet
    0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz
    #$%&@?!()[]<>{}=*+|-/~^_:;,.
Grid size: n = len(body) // 2.
"""

# 90-character column alphabet: 62 alphanumerics + 28 extended characters
vals = {}
for v, ch in enumerate('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                       'abcdefghijklmnopqrstuvwxyz'):
    vals[ch] = v
for v, ch in enumerate('#$%&@?!()[]<>{}=*+|-/~^_:;,.'):
    vals[ch] = 62 + v

IGN = "'"
SYMM = '.:/-ox+*c?'
SYMM_NAME = ['iden', 'rot2', 'dia1', 'ort1', 'rot4', 'dia2', 'ort2',
             'full', 'rct4', '????']


def decode_line(line):
    """Decode one line to (n, symmetry_name, frozenset_of_points)."""
    line = line.strip()
    if not line:
        return None
    sym = SYMM_NAME[SYMM.index(line[0])] if line[0] in SYMM else 'unknown'
    body = line[1:]
    n = len(body) // 2
    pts = []
    for h, ch in enumerate(body):
        if ch == IGN:
            continue
        row = h // 2
        col = vals[ch]
        pts.append((row, col))
    return n, sym, frozenset(pts)
