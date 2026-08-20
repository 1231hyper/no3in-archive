"""Fresh decoder for Flammenkamp's no-three-in-line class database.

Implemented from the published format specification (source page section
"About the implemented Algorithm", page revision 2026-08-19) — NOT from
the primary parser in src/parser/.  Independent code path by design.

Specification (quoted from the source page, verbatim where possible):

  "Now each configuration is lead in by a symmetry-class character of
   the list (. : / - o c x + *) which indicates the symmetry
   (iden rot2 dia1 ort1 rot4 rct4 dia2 ort2 full) respectively.
   Further, the selected positions are indicated by the alphabet
   0,1,2,...,9,A,B,C...,Z,a,b,...,z only in their column positions from
   top to bottom row and in every row from left to right.  [Each row of
   the grid contributes its two occupied columns, left to right; rows
   top to bottom; the configuration is terminated by a newline.]
   In February 2026 ... the alphabet was extended by 28 more characters.
   Thus the alphabet for encoding is now
   " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz
     #$%&@?!()[]<>{}=*+|-/~^_:;,. "
   It consists of 90 characters ..."

The page's quoted alphabet transcribes with a leading space; a space can
never be a column code (configurations are line-terminated and code
positions are aligned), so the 90-character alphabet that actually
occurs in the database is the string ALPHABET below (index 0..89).
Grid size: n = len(body) // 2, since each of the n rows contributes
exactly two column codes.
"""

ALPHABET = ("0123456789"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "abcdefghijklmnopqrstuvwxyz"
            "#$%&@?!()[]<>{}=*+|-/~^_:;,.")
assert len(ALPHABET) == 90

CODE = {ch: i for i, ch in enumerate(ALPHABET)}

MARKER_NAMES = {
    '.': 'iden', ':': 'rot2', '/': 'dia1', '-': 'ort1',
    'o': 'rot4', 'c': 'rct4', 'x': 'dia2', '+': 'ort2', '*': 'full',
}


class DecodeError(ValueError):
    pass


def decode_line(line):
    """Decode one database line to (n, marker, points).

    points is a tuple of (row, column) pairs, rows/columns in 0..n-1.
    Raises DecodeError on malformed input.
    """
    s = line.rstrip("\r\n")
    if not s:
        raise DecodeError("empty line")
    marker = s[0]
    if marker not in MARKER_NAMES:
        raise DecodeError("unknown marker %r" % marker)
    body = s[1:]
    if len(body) % 2 != 0:
        raise DecodeError("odd body length %d" % len(body))
    n = len(body) // 2
    if n < 2:
        raise DecodeError("n < 2")
    pts = []
    for pos, ch in enumerate(body):
        if ch not in CODE:
            raise DecodeError("illegal column code %r" % ch)
        col = CODE[ch]
        if col >= n:
            raise DecodeError("column code %d >= n=%d" % (col, n))
        pts.append((pos // 2, col))
    # exactly two points per row and per column is the 2n-structure
    row_count = [0] * n
    col_count = [0] * n
    for r, c in pts:
        row_count[r] += 1
        col_count[c] += 1
    bad_rows = [r for r in range(n) if row_count[r] != 2]
    bad_cols = [c for c in range(n) if col_count[c] != 2]
    if bad_rows or bad_cols:
        raise DecodeError(
            "degree violation rows=%r cols=%r" % (bad_rows, bad_cols))
    return n, MARKER_NAMES[marker], tuple(sorted(pts))
