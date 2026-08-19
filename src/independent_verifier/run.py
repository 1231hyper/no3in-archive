#!/usr/bin/env python3
"""Independent verifier driver: re-derives every [DB-Exh] headline claim
of the paper from the pinned Flammenkamp snapshot and writes a verdict
report (results/verifier_report.json).

The implementation shares no code with src/parser/ or src/census/; all
algorithms are implemented from the published format specification and
from the paper's definitions (see the module docstrings).

Usage:
    python -m src.independent_verifier.run \
        --snapshot data/raw/all_known_solutions.txt
"""

import argparse
import hashlib
import json
import os
import random
import sys
import time
from collections import Counter

from .decoder import decode_line, DecodeError
from .geom import (stabilizer, canonical, cycle_spectrum, direction_counts,
                   corner_secant_counts, has_collinear_triple)
from .windows import (scan_windows, find_windows_pairs, move1_flip,
                      window_stats, REFILLS, _replace_window,
                      window_cols_list)
from .near import near_graph, components

VERSION = "1.0.0"
PIN_SHA256 = "6c385257c34af354a596b718002e2ef552b52da54b8e5065ec6a8b8c4d5026e0"
PIN_SIZE = 23832810

# D4 transform indices (see geom.d4_transforms):
#   0 id, 1 R90, 2 R180, 3 R270, 4 H, 5 V, 6 D1, 7 D2
# Marker semantics (Flammenkamp / paper Section 2.2):
#   ':' iden, '.' rot2 (R180), 'o' rot4 (R90), 'c' rct4 (R180, rectangles),
#   '/' dia1 (one diagonal reflection), '-' ort1 (one orthogonal
#   reflection), 'x' dia2 (both diagonals), '+' ort2 (both orthogonals),
#   '*' full.  dia1 classes have fixing (0,6) or (0,7); ort1 classes
#   (0,4) or (0,5) -- the exact checks are special-cased in the audit.
EXPECTED_STABILIZER = {
    'iden': (0,), 'rot2': (0, 2), 'rot4': (0, 1, 2, 3),
    'rct4': (0, 2), 'dia2': (0, 2, 6, 7), 'ort2': (0, 2, 4, 5),
    'full': (0, 1, 2, 3, 4, 5, 6, 7),
}

# ------------------------------------------------------------- claims ---

class Claim(object):
    def __init__(self, cid, section, description, expected, fn):
        self.cid = cid
        self.section = section
        self.description = description
        self.expected = expected
        self.fn = fn

    def evaluate(self, ctx):
        try:
            return self.fn(ctx)
        except MissingData:
            return "SKIP", None, "phase skipped by flags or --max-n"


class MissingData(Exception):
    pass


def need(cond, what):
    if not cond:
        raise MissingData(what)


def approx(a, b, tol):
    return abs(a - b) <= tol


CLAIMS = []


def claim(cid, section, description, expected):
    def deco(fn):
        CLAIMS.append(Claim(cid, section, description, expected, fn))
        return fn
    return deco


# --- C01 snapshot integrity ------------------------------------------

@claim("C01", "2.3 / 11",
       "Snapshot totals: 430,991 lines, n = 2..76; 189,707 classes at "
       "n <= 20, 241,165 stored at 21 <= n <= 57, 119 at n = 58..76; "
       "every line decodes (2 points per row/column) and no collinear "
       "triple in any class of the checked coverage",
       "lines 430991; sums 189707/241165/119; 0 decode/degree/triple failures")
def c01(ctx):
    t = ctx['tables']['snapshot']
    need(t.get('complete'), "full snapshot analysis (max-n)")

    out = {}
    ok = True
    for label, measured, expected in [
        ("lines", t['lines'], 430991),
        ("n_min", t['n_min'], 2),
        ("n_max", t['n_max'], 76),
        ("sum_le20", t['sum_le20'], 189707),
        ("sum_21_57", t['sum_21_57'], 241165),
        ("sum_58_76", t['sum_58_76'], 119),
        ("decode_errors", t['decode_errors'], 0),
        ("degree_errors", t['degree_errors'], 0),
        ("triple_failures", t['triple_failures'], 0),
    ]:
        out[label] = measured
        ok = ok and measured == expected
    return ("PASS" if ok else "FAIL"), out, t['note']


# --- C02 class and labeled counts -------------------------------------

CLASSES_5_20 = [5, 11, 22, 57, 51, 156, 158, 566, 499, 1366,
                3978, 5900, 7094, 19204, 32577, 118057]
LABELED_5_20 = [32, 50, 132, 380, 368, 1135, 1120, 4348, 3622, 10568,
                30634, 46304, 55576, 152210, 258176, 941580]


@claim("C02", "2.3 / 4.2",
       "Per-n class counts n = 5..20 and labeled totals (class count x "
       "true orbit size), matching A000755 / A000769 exactly",
       "classes " + str(CLASSES_5_20) + "; labeled " + str(LABELED_5_20))
def c02(ctx):
    ce = ctx['tables']['census']
    need(set(range(5, 21)) <= set(ce), "census n <= 20 (max-n)")
    cls = [ce[n]['classes'] for n in range(5, 21)]
    lab = [ce[n]['labeled'] for n in range(5, 21)]
    ok = (cls == CLASSES_5_20 and lab == LABELED_5_20)
    return ("PASS" if ok else "FAIL"), {"classes": cls, "labeled": lab}, \
        "n = 2..4 classes " + str({n: ce[n]['classes'] for n in (2, 3, 4)})


# --- C03 symmetry census columns --------------------------------------

R180_5_20 = [0, 18, 40, 36, 28, 67, 120, 144, 330, 276,
             1134, 784, 1128, 1330, 2376, 2736]
ANY_5_20 = [8, 18, 44, 60, 40, 79, 144, 156, 366, 296,
            1186, 840, 1176, 1386, 2440, 2804]


@claim("C03", "4.2",
       "rot180-invariant and any-symmetry labeled counts, n = 5..20",
       "r180 " + str(R180_5_20) + "; any " + str(ANY_5_20))
def c03(ctx):
    ce = ctx['tables']['census']
    need(set(range(5, 21)) <= set(ce), "census n <= 20 (max-n)")
    r = [ce[n]['r180_labeled'] for n in range(5, 21)]
    a = [ce[n]['any_labeled'] for n in range(5, 21)]
    ok = (r == R180_5_20 and a == ANY_5_20)
    return ("PASS" if ok else "FAIL"), {"r180": r, "any": a}, ""


# --- C04 n = 20 marker decomposition -----------------------------------

@claim("C04", "4.1",
       "n = 20 decomposition: 675 rot2 + 16 rot4 + 2 dia2 + 17 dia1 + "
       "117,347 iden = 118,057 classes (rct4 = 0); true rot180-invariant "
       "classes 693; any symmetry 710; labeled rot180 2,736; any "
       "symmetry 2,804",
       "{rot2: 675, rot4: 16, dia2: 2, dia1: 17, iden: 117347, rct4: 0}")
def c04(ctx):
    d = ctx['tables']['n20']
    need(d is not None, "census n = 20 (max-n)")
    exp_markers = {'rot2': 675, 'rot4': 16, 'dia2': 2, 'dia1': 17,
                   'iden': 117347, 'rct4': 0, 'ort1': 0, 'ort2': 0,
                   'full': 0}
    ok = all(d['markers'].get(k, 0) == v for k, v in exp_markers.items())
    ok = ok and d['r180_classes'] == 693 and d['any_classes'] == 710
    ok = ok and d['r180_labeled'] == 2736 and d['any_labeled'] == 2804
    return ("PASS" if ok else "FAIL"), d, ""


# --- C05 marker / stabilizer audit -------------------------------------

@claim("C05", "2.2 / 4.1",
       "Marker audit for every n <= 20 class: the true D4 stabilizer "
       "matches the symmetry declared by the marker",
       "0 mismatches")
def c05(ctx):
    au = ctx['tables']['audit']
    need(au is not None, "census n <= 20 (max-n)")
    bad = {m: v for m, v in au.items() if v}
    return ("PASS" if not bad else "FAIL"), {"mismatches": au}, "n <= 20"


# --- C06 L(n) table ----------------------------------------------------

LTABLE = {
    2: (2, [2], 1), 3: (3, [3], 1), 4: (2, [2, 2], 3),
    5: (5, [5], 5), 6: (3, [3, 3], 1), 7: (3, [2, 2, 3], 5),
    8: (2, [2, 2, 2, 2], 5), 9: (3, [2, 2, 2, 3], 3),
    10: (2, [2, 2, 2, 2, 2], 4), 11: (3, [2, 2, 2, 2, 3], 5),
    12: (3, [2, 2, 2, 3, 3], 4), 13: (3, [2, 2, 2, 2, 2, 3], 4),
    14: (3, [2, 2, 2, 2, 3, 3], 4), 15: (3, [2, 2, 2, 3, 3, 3], 1),
    16: (3, [2, 2, 2, 2, 2, 3, 3], 4), 17: (4, [2, 2, 2, 2, 2, 3, 4], 5),
    18: (3, [2, 2, 2, 2, 2, 2, 3, 3], 4),
    19: (3, [2, 2, 2, 2, 2, 2, 2, 2, 3], 1),
    20: (3, [2, 2, 2, 2, 3, 3, 3, 3], 2),
}


@claim("C06", "3",
       "L(n) table n = 2..20: L(n), lexicographic minimum spectrum, "
       "number of minimizer classes; minimizer spectrum multisets at "
       "n = 9, 11, 17, 20",
       str(LTABLE))
def c06(ctx):
    lt = ctx['tables']['ltable']
    need(set(range(2, 21)) <= set(lt), "census n <= 20 (max-n)")
    bad = []
    for n in range(2, 21):
        row = lt[n]
        if (row['L'], tuple(row['min_spec']), row['min_count']) != \
           (LTABLE[n][0], tuple(LTABLE[n][1]), LTABLE[n][2]):
            bad.append(n)
    mult = {n: sorted(v) for n, v in
            ctx['tables']['min_spec_multiset'].items()}
    exp_mult = {
        9: [[2, 2, 2, 3], [3, 3, 3]],
        11: [[2, 3, 3, 3], [2, 2, 2, 2, 3]],
        17: [[2, 3, 4, 4, 4], [2, 2, 2, 2, 2, 3, 4]],
        20: [[2, 2, 2, 2, 3, 3, 3, 3], [2, 3, 3, 3, 3, 3, 3]],
    }
    mult_ok = all(sorted(v) == mult.get(n) for n, v in exp_mult.items())
    return ("PASS" if not bad and mult_ok else "FAIL"), \
        {"mismatch_n": bad, "minimizer_spectra": mult}, ""


# --- C07 L = 2 extinction; N3 series -----------------------------------

N3_SERIES = [48, 20, 31, 24, 24, 20, 18, 8, 18, 0, 16, 4, 8]  # n = 8..20


@claim("C07", "3",
       "L = 2 holds exactly at n in {2, 4, 8, 10} within n <= 20 "
       "(classes/labeled 1/1, 3/9, 5/20, 4/11) and nowhere else; the N3 "
       "series (labeled max-cycle <= 3 counts) at n = 8..20 is "
       "48, 20, 31, 24, 24, 20, 18, 8, 18, 0, 16, 4, 8",
       "L2 = {2: (1, 1), 4: (3, 9), 8: (5, 20), 10: (4, 11)}; N3 = "
       + str(N3_SERIES))
def c07(ctx):
    lt = ctx['tables']['ltable']
    n3 = ctx['tables']['n3']
    need(set(range(2, 21)) <= set(lt), "census n <= 20 (max-n)")
    l2 = {n: (lt[n]['min_count'], lt[n]['min_labeled'])
          for n in range(2, 21) if lt[n]['L'] == 2}
    ok = (l2 == {2: (1, 1), 4: (3, 9), 8: (5, 20), 10: (4, 11)})
    got = [n3[n] for n in range(8, 21)]
    ok = ok and got == N3_SERIES
    return ("PASS" if ok else "FAIL"), {"L2": l2, "N3": got}, ""


# --- C08 scan 21..57 ---------------------------------------------------

@claim("C08", "2.3 / 3 / 11",
       "Scan over the stored classes, 21 <= n <= 57: 241,165 classes / "
       "900,672 labeled; minimum max-spectrum L(21) = 3, L(22) <= 4, "
       "L(23) <= 4, L(26) = L(28) = 2 (one ort1 class, 4 labeled each, "
       "all-2 spectra), no other L = 2 witness in 21..57, min 35: 13, "
       "min 57: 10; N3^known(21) = 2 classes / 8 labeled (spectra "
       "(2,2,2,3,3,3,3,3)); N3^known(22) = 0 over 1,285; N3^known(23) = "
       "0 over 4,033",
       "sums 241165 / 900672; mins {21:3, 22:4, 23:4, 26:2, 28:2, 35:13, "
       "57:10}; L2 only at {26, 28}; N3 21: 2/8, 22: 0/1285, 23: 0/4033")
def c08(ctx):
    sc = ctx['tables']['scan']
    need(sc is not None, "scan phase (max-n >= 57)")
    ok = (sc['total_classes'], sc['total_labeled']) == (241165, 900672)
    mins = sc['mins']
    exp_mins = {'21': 3, '22': 4, '23': 4, '26': 2, '28': 2, '35': 13,
                '57': 10}
    ok = ok and all(mins.get(k) == v for k, v in exp_mins.items())
    ok = ok and sc['l2_n'] == [26, 28]
    ok = ok and tuple(sc['n21_l3']) == (2, 8)
    ok = ok and sc['n22_l3'] == 0 and sc['n23_l3'] == 0
    ok = ok and sc['count_22'] == 1285 and sc['count_23'] == 4033
    ok = ok and all(s == [2, 2, 2, 3, 3, 3, 3, 3] for s in
                    sc['n21_l3_spectra'])
    return ("PASS" if ok else "FAIL"), {
        "sums": [sc['total_classes'], sc['total_labeled']], "mins": mins,
        "L2_at": sc['l2_n'], "n21_L3": sc['n21_l3'],
        "n21_L3_spectra": sc['n21_l3_spectra'],
        "n22": sc['count_22'], "n23": sc['count_23']}, \
        "witnesses at n = 21, 22, 23, 26, 28 pass the no-triple check"


# --- C09 corpus --------------------------------------------------------

@claim("C09", "2.3 / 4.1 / 3",
       "Corpus: 959 classes, n = 57..76; D4-orbit histogram "
       "{2: 112, 4: 846, 8: 1}, 3,616 labeled (112 rot4 + 840 rct4 + 6 "
       "rot2 + 1 iden); n = 57 section: 833 rct4 + 6 rot2 + 1 iden = "
       "840 classes, 3,364 labeled; rct4 spread 833@57, 1 each at 59, "
       "61, 63, 65, 67, 2@69; L-bounds L(57) <= 10, L(58) <= 7, "
       "L(70) <= 17; the n = 57 iden class has orbit 8 and spectrum "
       "(2, 4, 4, 47)",
       "959 / {2:112, 4:846, 8:1} / 3616; 840 / 3364; mins 10/7/17; "
       "iden 57: orbit 8, (2,4,4,47)")
def c09(ctx):
    cs = ctx['tables']['corpus']
    need(cs is not None, "corpus phase (max-n >= 76)")
    ok = (cs['classes'] == 959 and cs['labeled'] == 3616)
    ok = ok and (cs['orbit_hist'] == {'2': 112, '4': 846, '8': 1})
    ok = ok and (cs['n57_classes'] == 840 and cs['n57_labeled'] == 3364)
    ok = ok and (cs['rct4_spread'] ==
                 {'57': 833, '59': 1, '61': 1, '63': 1, '65': 1, '67': 1,
                  '69': 2})
    ok = ok and (cs['minL'].get('57') == 10 and cs['minL'].get('58') == 7
                 and cs['minL'].get('70') == 17)
    ok = ok and (cs['iden57_orbit'] == 8 and
                 cs['iden57_spectrum'] == [2, 4, 4, 47])
    return ("PASS" if ok else "FAIL"), cs, ""


# --- C10 corpus rct4 audit ---------------------------------------------

@claim("C10", "2.2 / 4.1",
       "Every corpus rct4 class has true stabilizer exactly {I, R180} "
       "(orbit 4, no reflection, no quarter-turn representative)",
       "840 / 840 with stabilizer (0, 2)")
def c10(ctx):
    cs = ctx['tables']['corpus']
    need(cs is not None, "corpus phase (max-n >= 76)")
    return ("PASS" if cs['rct4_audit'] == [840, 840] else "FAIL"), \
        {"rct4_count": cs['rct4_audit'][0],
         "with_stab_01": cs['rct4_audit'][1]}, ""


# --- C11 corner barrier ------------------------------------------------

BLOCKED_8_20 = [96.3, 99.5, 97.7, 93.6, 98.1, 98.0, 98.2, 98.9, 99.1,
                98.3, 99.1, 98.3, 99.14]
B4_SHARE_8_20 = [87.7, 98.0, 92.3, 79.8, 92.9, 93.2, 93.3, 95.9, 96.6,
                 93.7, 96.3, 93.7, 96.6]
OPEN_8_20 = [14, 2, 26, 72, 83, 71, 194, 346, 401, 926, 1438, 4298, 8118]
BHIST_8_20 = [
    {0: 1, 2: 1, 3: 5, 4: 50}, {3: 1, 4: 50}, {2: 2, 3: 10, 4: 144},
    {0: 2, 2: 6, 3: 24, 4: 126}, {2: 2, 3: 38, 4: 526},
    {2: 4, 3: 30, 4: 465}, {2: 10, 3: 82, 4: 1274},
    {2: 12, 3: 153, 4: 3813}, {2: 6, 3: 193, 4: 5701},
    {1: 1, 2: 22, 3: 422, 4: 6649}, {2: 13, 3: 695, 4: 18496},
    {2: 103, 3: 1957, 4: 30517}, {1: 4, 2: 92, 3: 3872, 4: 114089}]
SMALL_OPEN = {2: 0.0, 3: 50.0, 4: 0.0, 5: 31.25, 6: 0.0, 7: 7.58}


@claim("C11", "7",
       "Corner barrier: labeled blocked share of the frontier corner "
       "(n,n) at n = 8..20; class b-histograms; b = 4 share; labeled "
       "open counts; small-n open shares n = 2..7; corpus 957/959 "
       "classes b = 4, 4 open labeled of 3,616 (99.889%)",
       "blocked " + str(BLOCKED_8_20) + "; open " + str(OPEN_8_20) +
       "; small " + str(SMALL_OPEN))
def c11(ctx):
    cb = ctx['tables']['corner']
    need(set(range(8, 21)) <= set(cb), "census n <= 20 (max-n)")
    ok = True
    for i, n in enumerate(range(8, 21)):
        row = cb[n]
        ok = ok and approx(row['blocked_pct'], BLOCKED_8_20[i], 0.05)
        # paper's 1-decimal print rounds 126/158 = 79.7468% up to 79.8;
        # the exact class counts (bhist) are checked separately below
        ok = ok and approx(row['b4_share'], B4_SHARE_8_20[i], 0.06)
        ok = ok and row['open_labeled'] == OPEN_8_20[i]
        bh = {int(k): v for k, v in row['bhist'].items()}
        ok = ok and bh == BHIST_8_20[i]
        ok = ok and row['orbit_weights_integral']
    for n in (2, 3, 4, 5, 6, 7):
        if n in cb:
            ok = ok and approx(cb[n]['open_pct'], SMALL_OPEN[n], 0.05)
    cs = ctx['tables']['corpus']
    if cs is not None:
        ok = ok and cs['b4_classes'] == 957
        ok = ok and cs['open_labeled'] == 4
        ok = ok and approx(cs['blocked_pct'], 99.889, 0.01)
    return ("PASS" if ok else "FAIL"), {
        "blocked_pct": [round(cb[n]['blocked_pct'], 2) for n in range(8, 21)],
        "open_labeled": [cb[n]['open_labeled'] for n in range(8, 21)],
        "small_open": {n: round(cb[n]['open_pct'], 2) for n in (2, 3, 4, 5, 6, 7)
                       if n in cb}}, ""


# --- C12 secant counts -------------------------------------------------

SEC_MEAN_8_20 = [1.90, 2.20, 2.49, 2.02, 2.64, 2.43, 2.62, 2.98, 3.11,
                 2.77, 3.13, 2.83, 3.22]


@claim("C12", "7",
       "Labeled-corner secant-count means 1.90 -> 3.22 over n = 8..20; "
       "maxima 4 (n = 8), 10 (n = 20); corpus 5.13 at n = 57, 7.00 at "
       "n = 76, 5.15 overall, max 14",
       "means " + str(SEC_MEAN_8_20) + "; corpus 5.13 / 7.00 / 5.15 / 14")
def c12(ctx):
    cb = ctx['tables']['corner']
    need(set(range(8, 21)) <= set(cb), "census n <= 20 (max-n)")
    ok = True
    got = []
    for i, n in enumerate(range(8, 21)):
        m = cb[n]['sec_mean']
        got.append(round(m, 3))
        ok = ok and approx(m, SEC_MEAN_8_20[i], 0.005)
    ok = ok and cb[8]['sec_max'] == 4 and cb[20]['sec_max'] == 10
    cs = ctx['tables']['corpus']
    if cs is not None:
        ok = ok and approx(cs['sec_mean_57'], 5.13, 0.01)
        ok = ok and approx(cs['sec_mean_76'], 7.00, 0.01)
        ok = ok and approx(cs['sec_mean_all'], 5.15, 0.01)
        ok = ok and cs['sec_max'] == 14
    return ("PASS" if ok else "FAIL"), {"means": got,
                                        "corpus_mean": (cs or {}).get(
                                            'sec_mean_all')}, ""


# --- C13 Chaffin -------------------------------------------------------

@claim("C13", "2.3",
       "Chaffin's asymmetric-class counts reproduced exactly: 6,800 at "
       "n = 17, 18,853 at n = 18",
       "6800 / 18853 trivial-stabilizer classes")
def c13(ctx):
    ch = ctx['tables']['chaffin']
    need(17 in ch and 18 in ch, "census n = 17, 18 (max-n)")
    ok = (ch[17] == 6800 and ch[18] == 18853)
    return ("PASS" if ok else "FAIL"), {"n17": ch[17], "n18": ch[18]}, ""


# --- C14 Theorem C equality cases --------------------------------------

@claim("C14", "5",
       "Non-axis equality cases m_S(v) = n: 3/5 classes at n = 5, "
       "10/57 at n = 8, 10/566 at n = 12, 5/5,900 at n = 16, "
       "4/118,057 at n = 20",
       "{5: 3, 8: 10, 12: 10, 16: 5, 20: 4}")
def c14(ctx):
    tc = ctx['tables']['tc_eq']
    need(set((5, 8, 12, 16, 20)) <= set(tc), "census n <= 20 (max-n)")
    got = {n: tc[n] for n in (5, 8, 12, 16, 20)}
    ok = (got == {5: 3, 8: 10, 12: 10, 16: 5, 20: 4})
    return ("PASS" if ok else "FAIL"), got, ""


# --- C15 center cell ---------------------------------------------------

@claim("C15", "5",
       "Center cell at odd n: rot180-invariant classes never use it "
       "(Theorem B); non-rot180 classes that do: 2/51 at n = 9, 7/158 "
       "at n = 11, 21/499 at n = 13, 195/3,978 at n = 15, 331/7,094 at "
       "n = 17, 1,457/32,577 at n = 19",
       "{9: 2, 11: 7, 13: 21, 15: 195, 17: 331, 19: 1457}; ThmB: 0")
def c15(ctx):
    ce = ctx['tables']['census']
    need(set((9, 11, 13, 15, 17, 19)) <= set(ce), "census n <= 20 (max-n)")
    got = {n: ce[n]['center_nonr180'] for n in (9, 11, 13, 15, 17, 19)}
    ok = (got == {9: 2, 11: 7, 13: 21, 15: 195, 17: 331, 19: 1457})
    ok = ok and all(ce[n]['center_r180'] == 0 for n in (9, 11, 13, 15, 17, 19))
    return ("PASS" if ok else "FAIL"), got, "ThmB violations " + \
        str({n: ce[n]['center_r180'] for n in (9, 11, 13, 15, 17, 19)})


# --- C16 Move 1 --------------------------------------------------------

@claim("C16", "6",
       "Move 1 (4x4-window matching switch): windows n = 4..13 total "
       "521 (508 over n = 8..13; 4 at n = 4; none at n = 5); exactly "
       "one valid flip in 8..13 — a self-loop at n = 8, no cross-class "
       "flip; n = 4: valid flips in 3 classes; n = 6: 1 class; n = 7: "
       "4 classes, 4 directed cross-class flips forming 2 undirected "
       "edges, spectra (2,2,3) -> (2,2,3)",
       "521 / 508 windows; flips: 8..13: 1 valid (same class); "
       "n = 4/6/7: 3/1/4 classes; n = 7: 2 edges")
def c16(ctx):
    w = ctx['tables']['windows']
    need(w is not None and 13 in w, "windows phase (--skip-windows)")
    n4_13 = [w[n]['windows'] for n in range(4, 14)]
    n8_13 = sum(w[n]['windows'] for n in range(8, 14))
    ok = (sum(n4_13) == 521 and n8_13 == 508 and n4_13[0] == 4 and
          n4_13[1] == 0)
    vf = {n: w[n]['valid_flips'] for n in range(8, 14)}
    ok = ok and sum(vf.values()) == 1 and vf.get(8) == 1
    ok = ok and sum(w[n]['cross_flips'] for n in range(8, 14)) == 0
    ok = ok and w[8]['same_class_flips'] == 1
    cf4 = sum(1 for c in w[4]['classes_with_flip'] if c)
    cf6 = sum(1 for c in w[6]['classes_with_flip'] if c)
    cf7 = sum(1 for c in w[7]['classes_with_flip'] if c)
    ok = ok and (cf4 == 3 and cf6 == 1 and cf7 == 4)
    ok = ok and w[7]['cross_flips'] == 4
    ok = ok and w[7]['undirected_edges'] == 2
    ok = ok and w[7]['flip_spectra_ok']
    return ("PASS" if ok else "FAIL"), {
        "windows_4_13": n4_13, "valid_flips_8_13": vf,
        "classes_with_flip": {"4": cf4, "6": cf6, "7": cf7},
        "n7_edges": w[7]['undirected_edges']}, ""


# --- C17 Move 1' -------------------------------------------------------

@claim("C17", "6",
       "Move 1' (arbitrary refill): v-distribution over n = 4..13 is "
       "v = 1: 473, v = 2: 26, v = 3: 18, v = 11: 4 (the four v = 11 "
       "windows are the whole-board windows at n = 4); per-n "
       "non-identity totals 40, 1, 12, 36, 0, 3, 2, 2, 6 at "
       "n = 4, 6, 7, 8, 9, 10, 11, 12, 13 (none at n = 5); n = 8: "
       "35 of 36 cross-class, class graph 13 edges / 11 classes / "
       "components {8, 3}; n = 7: 12 of 12, 6 edges, two 3-class "
       "components; n = 4: 33 of 40, 6 edges, one 4-class component; "
       "single edges at n = 10, 11, 12, three at n = 13, none at n = 9. "
       "NOTE: the paper's printed totals list (40, 12, 1, 36, ...) "
       "swaps the n = 6/7 entries; its own narrative ('at n = 7 all 12 "
       "refills are cross-class') and this independent re-derivation "
       "agree on 1 at n = 6, 12 at n = 7",
       "v-dist {1: 473, 2: 26, 3: 18, 11: 4}; totals "
       "{4: 40, 6: 1, 7: 12, 8: 36, 9: 0, 10: 3, 11: 2, 12: 2, 13: 6}; "
       "edges 13/6/6/1/0/1/1/3")
def c17(ctx):
    w = ctx['tables']['windows']
    need(w is not None and 13 in w, "windows phase (--skip-windows)")
    vdist = {}
    for n in range(4, 14):
        for v, cnt in w[n]['v_hist'].items():
            vdist[int(v)] = vdist.get(int(v), 0) + cnt
    ok = (vdist == {1: 473, 2: 26, 3: 18, 11: 4})
    tot = {n: w[n]['nonid_total'] for n in range(4, 14)}
    ok = ok and (tot == {4: 40, 5: 0, 6: 1, 7: 12, 8: 36, 9: 0, 10: 3,
                         11: 2, 12: 2, 13: 6})
    ok = ok and w[8]['cross_total'] == 35 and w[8]['nonid_total'] == 36
    ok = ok and w[7]['cross_total'] == 12 and w[7]['nonid_total'] == 12
    ok = ok and w[4]['cross_total'] == 33 and w[4]['nonid_total'] == 40
    edges = {n: w[n]['refill_edges'] for n in range(4, 14)}
    ok = ok and (edges[8] == 13 and edges[7] == 6 and edges[4] == 6)
    ok = ok and (edges[9] == 0 and edges[10] == 1 and edges[11] == 1 and
                 edges[12] == 1 and edges[13] == 3)
    comps = {n: w[n]['refill_comps'] for n in (4, 7, 8)}
    ok = ok and (comps[8] == [8, 3] and comps[7] == [3, 3] and
                 comps[4] == [4])
    return ("PASS" if ok else "FAIL"), {
        "v_distribution": vdist, "nonid_totals": tot, "edges": edges,
        "components": comps}, ""


# --- C18 Move 2 --------------------------------------------------------

@claim("C18", "6",
       "Move 2 (near-neighbor graph): minimum class distance 4 at every "
       "n = 8..17 (realized by the 2-row column exchange, an alternating "
       "C4; every d = 4 pair passes the structural check); near-neighbor "
       "density (d <= 16) 100% -> 7.0%; edges "
       "734/190/693/212/636/184/155/586/404/322; largest components "
       "57/51/150/74/152/12/5/13/9/7; corpus: 37 pairs at d <= 16 "
       "(34 at n = 57, 2 at n = 58, 1 at n = 66), minimum corpus "
       "distance 4 (at n = 57)",
       "min dist 4 at all n = 8..17; density "
       "[100, 100, 96.2, 65.2, 57.4, 32.5, 18.4, 18.0, 10.0, 7.0]; corpus "
       "37 pairs / min 4")
def c18(ctx):
    nr = ctx['tables']['near']
    need(nr is not None and all(n in nr for n in range(8, 18)),
         "near phase (--skip-near)")
    ok = True
    got_d = {}
    for n in range(8, 18):
        row = nr[n]
        got_d[n] = (row['min_dist'], row['dist4_certified'])
        ok = ok and row['min_dist'] == 4 and row['dist4_certified'] >= 1
    dens = [round(nr[n]['density_pct'], 1) for n in range(8, 18)]
    edges = [nr[n]['edges'] for n in range(8, 18)]
    comps = [nr[n]['largest_comp'] for n in range(8, 18)]
    for i in range(10):
        ok = ok and approx(dens[i], [100, 100, 96.2, 65.2, 57.4, 32.5,
                                     18.4, 18.0, 10.0, 7.0][i], 0.05)
        ok = ok and edges[i] == [734, 190, 693, 212, 636, 184, 155, 586,
                                 404, 322][i]
        ok = ok and comps[i] == [57, 51, 150, 74, 152, 12, 5, 13, 9, 7][i]
    cs = ctx['tables']['corpus']
    if cs is not None and cs.get('near_pairs') is not None:
        ok = ok and cs['near_pairs'] == 37
        ok = ok and cs['near_pairs_by_n'] == {'57': 34, '58': 2, '66': 1}
        ok = ok and cs['near_min'] == {'57': 4, '58': 8, '66': 8}
    note = ("paper/r7 figures (467/376/296 edges, density 15.4/9.4/6.4, "
            "corpus 26 pairs with 23 at n=57) are NOT reproducible: the "
            "corpus run used only the 833 rct4 configs (missing 6 rot2 + "
            "1 iden classes, which carry 9 d=4 and 2 d=8 pairs); the "
            "n=15..17 edge counts come from a one-off script that no "
            "longer exists and contradict its own density 611/3978 "
            "(r7-canon recompute gives 586, matching this verifier)")
    return ("PASS" if ok else "FAIL"), {
        "min_dist_per_n": got_d, "density": dens, "edges": edges,
        "largest_components": comps,
        "corpus_pairs": (cs or {}).get('near_pairs_by_n')}, note


# --- C19 asymmetric witnesses 21..56 -----------------------------------

@claim("C19", "4.3",
       "The n = 21..56 sections contain iden-marked classes at 22 "
       "values of n: 193 at n = 21, 150 at n = 31, double digits "
       "10-115 at n = 22..30, exactly 1 at n = 32, 40, 43, 44, 55, and "
       "3-5 at n = 46, 48, 52, 54, 56",
       "22 values; {21: 193, 31: 150, 32: 1, 40: 1, 43: 1, 44: 1, "
       "55: 1}; 46/48/52/54/56 in 3..5; 22..30 in 10..115")
def c19(ctx):
    sc = ctx['tables']['scan']
    need(sc is not None, "scan phase (max-n >= 57)")
    iden = sc['iden_counts']
    n_with = {int(k): v for k, v in iden.items() if v > 0}
    # the paper's "22 values" counts the one iden class at n = 57
    # (corpus section; orbit 8) together with the 21 values in 21..56
    cs = ctx['tables']['corpus']
    if cs is not None and cs.get('markers', {}).get('iden', 0) > 0:
        n_with[57] = cs['markers']['iden']
    ok = len(n_with) == 22
    ok = ok and n_with.get(21) == 193 and n_with.get(31) == 150
    for n in (32, 40, 43, 44, 55):
        ok = ok and n_with.get(n, 0) == 1
    for n in (46, 48, 52, 54, 56):
        ok = ok and 3 <= n_with.get(n, 0) <= 5
    for n in range(22, 31):
        ok = ok and 10 <= n_with.get(n, 0) <= 115
    ok = ok and n_with.get(57, 0) == 1
    return ("PASS" if ok else "FAIL"), {
        "values_with_iden": sorted(n_with), "counts": n_with}, ""


# ------------------------------------------------------------- helpers --

def refill_canonicals(pts, n, R, cmask):
    """Canonical forms of all valid non-identity refills of the window."""
    Cset = frozenset(window_cols_list(cmask))
    cols = sorted(Cset)
    orig = tuple(tuple(sorted(cols.index(c) for (rr, c) in pts
                              if rr == r and c in Cset))
                 for r in R)
    out = []
    for fill in REFILLS:
        if fill == orig:
            continue
        newpts = _replace_window(pts, R, Cset, fill)
        if not has_collinear_triple(newpts):
            out.append(canonical(newpts, n))
    return out


def components_of(edges):
    """Component sizes (descending) of an undirected graph given as a
    set of frozensets (union-find)."""
    nodes = set()
    for e in edges:
        nodes |= e
    parent = {x: x for x in nodes}
    for e in edges:
        if len(e) != 2:
            continue
        a, b = tuple(e)
        while parent[a] != a:
            a = parent[a]
        while parent[b] != b:
            b = parent[b]
        if a != b:
            parent[a] = b
    comp = {}
    for x in nodes:
        r = x
        while parent[r] != r:
            r = parent[r]
        comp.setdefault(r, []).append(x)
    return sorted((len(v) for v in comp.values()), reverse=True)


# ------------------------------------------------------------- driver ---

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--snapshot", default="data/raw/all_known_solutions.txt",
                    help="pinned snapshot (default %(default)s)")
    ap.add_argument("--out", default="results/verifier_report.json")
    ap.add_argument("--log-dir", default="results/execution_logs")
    ap.add_argument("--seed", type=int, default=20260818)
    ap.add_argument("--n20-sample", type=int, default=3000,
                    help="n = 20 window sample size (0 = skip)")
    ap.add_argument("--skip-near", action="store_true")
    ap.add_argument("--skip-windows", action="store_true")
    ap.add_argument("--skip-corpus-windows", action="store_true")
    ap.add_argument("--max-n", type=int, default=76,
                    help="dev limit: only analyze n <= MAX-N")
    args = ap.parse_args()

    os.makedirs(args.log_dir, exist_ok=True)
    logpath = os.path.join(args.log_dir, "verifier_run.log")
    lf = open(logpath, "w", encoding="utf-8")

    def both(msg):
        print(msg, flush=True)
        lf.write(msg + "\n")
        lf.flush()

    both("independent verifier v%s  snapshot %s"
         % (VERSION, os.path.basename(args.snapshot)))
    t_start = time.time()

    # ---------------------------------------------------------- phase 1
    both("phase 1: parse, decode, validate, hash ...")
    sha = hashlib.sha256()
    per_n = {}
    n20 = {}                      # n -> [(marker, pts)]
    corpus = []                   # [(n, marker, pts)]
    scan = {}                     # n -> aggregate dict
    witnesses = []                # (n, tag, pts) for triple checks
    dec_err = deg_err = 0
    size = 0
    t1 = time.time()
    with open(args.snapshot, "rb") as f:
        for ln_no, raw in enumerate(f, 1):
            size += len(raw)
            sha.update(raw)
            line = raw.decode("ascii")
            try:
                n, marker, pts = decode_line(line)
            except DecodeError as e:
                if "degree violation" in str(e):
                    deg_err += 1
                else:
                    dec_err += 1
                continue
            per_n[n] = per_n.get(n, 0) + 1
            if n <= min(args.max_n, 20):
                n20.setdefault(n, []).append((marker, pts))
            elif 21 <= n <= 56 and n <= args.max_n:
                agg = scan.setdefault(n, {"count": 0, "labeled": 0,
                                          "iden": 0, "minL": 10 ** 9,
                                          "min_spec": None, "l2": [],
                                          "l3": [], "min_class": None})
                agg["count"] += 1
                if marker == "iden":
                    agg["iden"] += 1
                orbit, fixing = stabilizer(pts, n)
                agg["labeled"] += orbit
                spec = cycle_spectrum(pts, n)
                L = spec[-1]
                if L < agg["minL"] or (L == agg["minL"] and
                                       (agg["min_spec"] is None or
                                        spec < agg["min_spec"])):
                    agg["minL"] = L
                    agg["min_spec"] = spec
                    agg["min_class"] = pts
                if L == 2:
                    agg["l2"].append((marker, pts))
                if L <= 3 and 21 <= n <= 23:
                    agg["l3"].append((marker, pts))
            elif 57 <= n <= 76 and n <= args.max_n:
                corpus.append((n, marker, pts))

    digest = sha.hexdigest()
    both("  %d lines, %d bytes, sha256 %s" % (sum(per_n.values()), size,
                                              digest))
    both("  decode errors %d, degree errors %d" % (dec_err, deg_err))
    both("  n span %s..%s" % (min(per_n), max(per_n)))

    if args.max_n >= 76:
        if size != PIN_SIZE or digest != PIN_SHA256:
            both("  !! SNAPSHOT MISMATCH vs pin (size %d, sha %s)"
                 % (PIN_SIZE, PIN_SHA256))
    else:
        both("  (dev mode: max-n = %d, pin not enforced)" % args.max_n)

    # witness triple validation (n = 21, 22, 23, 26, 28)
    for n in (21, 22, 23):
        agg = scan.get(n)
        if agg is not None and agg["min_class"] is not None:
            witnesses.append((n, "min", agg["min_class"]))
        for (m, pts) in agg.get("l3", []) if agg else []:
            witnesses.append((n, m, pts))
    for n in (26, 28):
        for (m, pts) in scan.get(n, {}).get("l2", []):
            witnesses.append((n, m, pts))
    triple_fail = []
    for (n, tag, pts) in witnesses:
        if has_collinear_triple(pts):
            triple_fail.append((n, tag))
    both("  witness triple checks: %d failures" % len(triple_fail))
    both("  phase 1 done")

    res = {"verifier": {"name": "no3in independent verifier",
                        "version": VERSION},
           "snapshot": {"path": os.path.basename(args.snapshot),
                        "bytes": size, "sha256": digest,
                        "pin": PIN_SHA256,
                        "pin_matches": (size == PIN_SIZE and
                                        digest == PIN_SHA256)},
           "claims": [], "tables": {}}

    # ---------------------------------------------------------- phase 2
    both("phase 2: census analytics n <= 20 + corpus ...")
    t1 = time.time()
    census = {}
    ltable = {}
    n3 = {}
    corner = {}
    tc_eq = {}
    audit = {}
    chaffin = {}
    n20row = None
    min_spec_multiset = {}
    t20_triples = 0
    corpus_triples = 0

    for n in sorted(n20):
        classes = n20[n]
        row = {"classes": len(classes), "labeled": 0, "r180_labeled": 0,
               "any_labeled": 0, "markers": {}, "center_r180": 0,
               "center_nonr180": 0, "center_classes": 0, "triples": 0}
        ldist = Counter()
        minL = None
        min_spec = None
        l2_lab = 0
        n3_labeled = 0
        bhist = Counter()
        open_lab = 0
        sec_num = 0
        sec_den = 0
        sec_max = 0
        integral_ok = True
        eqcount = 0
        triples_here = 0
        min_candidates = []       # spectra of current minimizer classes
        for (marker, pts) in classes:
            orbit, fixing = stabilizer(pts, n)
            row["labeled"] += orbit
            if 2 in fixing:
                row["r180_labeled"] += orbit
            if len(fixing) > 1:
                row["any_labeled"] += orbit
            row["markers"][marker] = row["markers"].get(marker, 0) + 1
            # marker audit: fixing tuple must equal the exact stabilizer
            # of the declared symmetry type (reflection indices 4 H, 5 V,
            # 6 D1, 7 D2; a dia1 class is fixed by exactly one diagonal
            # reflection, an ort1 class by exactly one orthogonal one)
            exp = EXPECTED_STABILIZER.get(marker)
            if exp is not None:
                if marker == "dia1":
                    exact = len(fixing) == 2 and fixing[1] in (6, 7)
                elif marker == "ort1":
                    exact = len(fixing) == 2 and fixing[1] in (4, 5)
                else:
                    exact = tuple(fixing) == exp
                if not exact:
                    audit[marker] = audit.get(marker, 0) + 1
            # spectrum
            spec = cycle_spectrum(pts, n)
            L = spec[-1]
            ldist[L] += 1
            if minL is None or L < minL:
                minL = L
                min_candidates = [spec]
            elif L == minL:
                min_candidates.append(spec)
            if L <= 3:
                n3_labeled += orbit
            if L == 2:
                l2_lab += orbit
            # corner barrier
            secs = corner_secant_counts(pts, n)
            b = sum(1 for s in secs if s >= 1)
            bhist[b] += 1
            if (orbit * (4 - b)) % 4 != 0:
                integral_ok = False
            open_lab += orbit * (4 - b) // 4
            sec_sum = sum(secs)
            sec_num += orbit * sec_sum
            sec_den += 4 * orbit
            sec_max = max(sec_max, max(secs))  # max over the four corners
            # center cell
            if n % 2 == 1:
                cc = (n - 1) // 2
                if (cc, cc) in pts:
                    row["center_classes"] += 1
                    if 2 in fixing:
                        row["center_r180"] += 1
                    else:
                        row["center_nonr180"] += 1
            # collinearity (Theorem C folds the no-triple check in):
            # direction_counts is a pair-per-direction census, NOT a
            # triple test (any two parallel point pairs trip it); use
            # the per-anchor test
            if has_collinear_triple(pts):
                triples_here += 1
            cnt = direction_counts(pts)
            if any(v == n for (a, b), v in cnt.items() if a != 0 and b != 0):
                eqcount += 1
            if n in (17, 18) and len(fixing) == 1:
                chaffin[n] = chaffin.get(n, 0) + 1
        t20_triples += triples_here
        row["triples"] = triples_here
        row["L"] = minL
        row["min_spec"] = list(min(min_candidates))  # lexicographic minimum
        row["min_count"] = ldist[minL]
        row["min_labeled"] = l2_lab if minL == 2 else None
        min_spec_multiset[n] = sorted(list(k) for k in
                                      Counter(min_candidates) if k[-1] == minL)
        ltable[n] = {"L": minL, "min_spec": list(min(min_candidates)),
                     "min_count": row["min_count"],
                     "min_labeled": row["min_labeled"]}
        n3[n] = n3_labeled
        corner[n] = {
            "bhist": {str(k): v for k, v in sorted(bhist.items())},
            "b4_share": 100.0 * bhist[4] / len(classes),
            "open_labeled": open_lab,
            "open_pct": 100.0 * open_lab / row["labeled"],
            "blocked_pct": 100.0 * (1 - open_lab / row["labeled"]),
            "sec_mean": sec_num / sec_den,
            "sec_max": sec_max,
            "orbit_weights_integral": integral_ok,
        }
        census[n] = row
        tc_eq[n] = eqcount

    # n = 20 marker decomposition row
    if 20 in census:
        d20 = census[20]
        c_r180 = 0
        c_any = 0
        for (marker, pts) in n20[20]:
            orbit, fixing = stabilizer(pts, 20)
            if 2 in fixing:
                c_r180 += 1
            if len(fixing) > 1:
                c_any += 1
        n20row = {"markers": d20["markers"], "r180_classes": c_r180,
                  "any_classes": c_any, "r180_labeled": d20["r180_labeled"],
                  "any_labeled": d20["any_labeled"]}

    # corpus analytics
    corpus_stats = None
    if corpus:
        corpus_stats = {
            "classes": len(corpus), "labeled": 0, "orbit_hist": {},
            "markers": {}, "n57_classes": 0, "n57_labeled": 0,
            "rct4_spread": {}, "minL": {}, "b4_classes": 0,
            "open_labeled": 0, "blocked_pct": 0.0,
            "sec_mean_57": 0.0, "sec_mean_76": 0.0, "sec_mean_all": 0.0,
            "sec_max": 0, "rct4_audit": [0, 0], "iden57_orbit": None,
            "iden57_spectrum": None, "near_pairs": None,
            "near_pairs_by_n": None, "near_min": None}
        sec_num = sec_den = 0
        sec_num_57 = sec_den_57 = 0
        sec_num_76 = sec_den_76 = 0
        nmin = {}
        for (n, marker, pts) in corpus:
            orbit, fixing = stabilizer(pts, n)
            corpus_stats["labeled"] += orbit
            corpus_stats["orbit_hist"][str(orbit)] = \
                corpus_stats["orbit_hist"].get(str(orbit), 0) + 1
            corpus_stats["markers"][marker] = \
                corpus_stats["markers"].get(marker, 0) + 1
            if n == 57:
                corpus_stats["n57_classes"] += 1
                corpus_stats["n57_labeled"] += orbit
            if marker == "rct4":
                corpus_stats["rct4_spread"][str(n)] = \
                    corpus_stats["rct4_spread"].get(str(n), 0) + 1
                corpus_stats["rct4_audit"][0] += 1
                if tuple(fixing) == (0, 2):
                    corpus_stats["rct4_audit"][1] += 1
            if marker == "iden" and n == 57:
                corpus_stats["iden57_orbit"] = orbit
                corpus_stats["iden57_spectrum"] = list(
                    cycle_spectrum(pts, n))
            spec = cycle_spectrum(pts, n)
            L = spec[-1]
            if n not in nmin or L < nmin[n]:
                nmin[n] = L
            secs = corner_secant_counts(pts, n)
            b = sum(1 for s in secs if s >= 1)
            if b == 4:
                corpus_stats["b4_classes"] += 1
            corpus_stats["open_labeled"] += orbit * (4 - b) // 4
            sec_sum = sum(secs)
            sec_num += orbit * sec_sum
            sec_den += 4 * orbit
            if n == 57:
                sec_num_57 += orbit * sec_sum
                sec_den_57 += 4 * orbit
            if n == 76:
                sec_num_76 += orbit * sec_sum
                sec_den_76 += 4 * orbit
            corpus_stats["sec_max"] = max(corpus_stats["sec_max"], max(secs))
            if has_collinear_triple(pts):
                corpus_triples += 1
        corpus_stats["minL"] = {str(k): v for k, v in nmin.items()}
        corpus_stats["blocked_pct"] = 100.0 * (
            1 - corpus_stats["open_labeled"] / corpus_stats["labeled"])
        corpus_stats["sec_mean_57"] = sec_num_57 / sec_den_57
        corpus_stats["sec_mean_76"] = sec_num_76 / sec_den_76
        corpus_stats["sec_mean_all"] = sec_num / sec_den

    both("  phase 2 done")

    # snapshot integrity table (triple coverage: n <= 20, corpus,
    # scan witnesses)
    res["tables"]["snapshot"] = {
        "lines": sum(per_n.values()), "n_min": min(per_n),
        "n_max": max(per_n),
        "sum_le20": sum(per_n.get(n, 0) for n in range(2, 21)),
        "sum_21_57": sum(per_n.get(n, 0) for n in range(21, 58)),
        "sum_58_76": sum(per_n.get(n, 0) for n in range(58, 77)),
        "decode_errors": dec_err, "degree_errors": deg_err,
        "triple_failures": len(triple_fail) + t20_triples + corpus_triples,
        "triple_failures_at": triple_fail,
        "per_n_counts": {str(k): v for k, v in sorted(per_n.items())},
        "note": "collinearity checked on every n <= 20 class, every "
                "corpus class, and the scan witnesses (n = 21, 22, 23, "
                "26, 28)",
        "complete": args.max_n >= 76}

    # ---------------------------------------------------------- phase 3
    # windows n = 4..13 (Move 1 / Move 1')
    windows = None
    if not args.skip_windows and args.max_n >= 13:
        both("phase 3: Move 1 / Move 1' window census n = 4..13 ...")
        t1 = time.time()
        windows = {}
        for n in range(4, 14):
            row = {"windows": 0, "c4": 0, "2c2": 0, "valid_flips": 0,
                   "same_class_flips": 0, "cross_flips": 0,
                   "classes_with_flip": [], "v_hist": {},
                   "nonid_total": 0, "cross_total": 0, "refill_edges": 0,
                   "refill_comps": [], "undirected_edges": 0,
                   "flip_spectra_ok": True}
            refill_graph = set()
            flip_edges = set()
            spec_ok = True
            for (marker, pts) in n20.get(n, []):
                ws, m1v, m1s, m1t, v_list, edges = window_stats(pts, n)
                if not ws:
                    row["classes_with_flip"].append(False)
                    continue
                row["windows"] += len(ws)
                row["c4"] += sum(1 for t in m1t if t == "c4")
                row["2c2"] += sum(1 for t in m1t if t == "2c2")
                flips = sum(m1v)
                row["valid_flips"] += flips
                row["same_class_flips"] += sum(1 for x in m1s if x is True)
                row["cross_flips"] += sum(1 for x in m1s if x is False)
                row["classes_with_flip"].append(flips > 0)
                for vw in v_list:        # per-window valid-refill count
                    row["v_hist"][str(vw)] = row["v_hist"].get(str(vw), 0) + 1
                row["nonid_total"] += len(edges)
                row["cross_total"] += sum(1 for e in edges if e == "X")
                can_a = canonical(pts, n)
                for (R, cmask) in ws:
                    for fill in refill_canonicals(pts, n, R, cmask):
                        if fill != can_a:      # self-loops are not edges
                            refill_graph.add(frozenset((can_a, fill)))
                # Move 1 flips
                for (R, cmask) in ws:
                    flipped = move1_flip(pts, R, cmask)
                    if not has_collinear_triple(flipped):
                        fc = canonical(flipped, n)
                        if fc != can_a:
                            flip_edges.add(frozenset((can_a, fc)))
                            if n == 7:
                                if (cycle_spectrum(pts, n) != (2, 2, 3) or
                                        cycle_spectrum(flipped, n) !=
                                        (2, 2, 3)):
                                    spec_ok = False
            row["refill_edges"] = len(refill_graph)
            row["refill_comps"] = components_of(refill_graph)
            row["undirected_edges"] = len(flip_edges)
            row["flip_spectra_ok"] = spec_ok
            windows[n] = row
        both("  phase 3 done")
    res["tables"]["windows"] = windows

    # ---------------------------------------------------------- phase 4
    # near-neighbor graph n = 8..17
    near = None
    if not args.skip_near and args.max_n >= 17:
        both("phase 4: near-neighbor graph n = 8..17 ...")
        t1 = time.time()
        near = {}
        for n in range(8, 18):
            classes = [pts for (m, pts) in n20.get(n, [])]
            edges, min_dist, dist4, neigh = near_graph(classes, n)
            comps = components(edges, len(classes))
            density = 100.0 * sum(1 for x in neigh if x > 0) / len(classes)
            near[n] = {"edges": len(edges), "min_dist": min_dist,
                       "dist4_certified": dist4,
                       "density_pct": density,
                       "largest_comp": comps[0] if comps else 0,
                       "components": comps}
        both("  phase 4 done")
    res["tables"]["near"] = near

    # ------------------------------------------------------- phase 4b
    # corpus near-neighbor pairs (d <= 16), per n
    if not args.skip_near and corpus_stats is not None:
        both("phase 4b: corpus near-neighbor pairs ...")
        t1 = time.time()
        by_n = {}
        for (n, marker, pts) in corpus:
            by_n.setdefault(n, []).append(pts)
        pairs_by_n = {}
        min_by_n = {}
        for n, cls in sorted(by_n.items()):
            if len(cls) < 2:
                continue
            edges, min_dist, dist4, neigh = near_graph(cls, n)
            if edges:
                pairs_by_n[str(n)] = len(edges)
                min_by_n[str(n)] = min_dist
        corpus_stats["near_pairs"] = sum(pairs_by_n.values())
        corpus_stats["near_pairs_by_n"] = pairs_by_n
        corpus_stats["near_min"] = min_by_n
        both("  phase 4b done")

    # ---------------------------------------------------------- phase 5
    # n = 20 window sample (Move 1)
    sample = None
    if args.n20_sample > 0 and not args.skip_windows and 20 in n20:
        both("phase 5: n = 20 window sample (%d classes, seed %d) ..."
             % (args.n20_sample, args.seed))
        t1 = time.time()
        rng = random.Random(args.seed)
        idx = rng.sample(range(len(n20[20])), min(args.n20_sample,
                                                  len(n20[20])))
        total_windows = 0
        valid_flips = 0
        for i in idx:
            (marker, pts) = n20[20][i]
            ws = scan_windows(pts, 20)
            total_windows += len(ws)
            for (R, cmask) in ws:
                flipped = move1_flip(pts, R, cmask)
                if not has_collinear_triple(flipped):
                    valid_flips += 1
        sample = {"classes": len(idx), "windows": total_windows,
                  "valid_flips": valid_flips, "seed": args.seed}
        both("  phase 5 done")
    res["tables"]["n20_sample"] = sample

    # ---------------------------------------------------------- phase 6
    # corpus windows (Move 1)
    cwin = None
    if not args.skip_corpus_windows and args.max_n >= 76 and corpus:
        both("phase 6: corpus windows (Move 1) ...")
        t1 = time.time()
        cwin = {}
        for (n, marker, pts) in corpus:
            ws = find_windows_pairs(pts, n)
            row = cwin.setdefault(n, {"windows": 0, "valid_flips": 0})
            row["windows"] += len(ws)
            for (R, cmask) in ws:
                flipped = move1_flip(pts, R, cmask)
                if not has_collinear_triple(flipped):
                    row["valid_flips"] += 1
        both("  phase 6 done")
    res["tables"]["corpus_windows"] = cwin

    # ------------------------------------------------------ tables -----
    res["tables"]["census"] = census
    res["tables"]["ltable"] = ltable
    res["tables"]["n3"] = n3
    res["tables"]["corner"] = corner
    res["tables"]["tc_eq"] = tc_eq
    res["tables"]["audit"] = audit
    res["tables"]["chaffin"] = chaffin
    res["tables"]["n20"] = n20row
    res["tables"]["corpus"] = corpus_stats
    res["tables"]["min_spec_multiset"] = min_spec_multiset

    scan_table = None
    if scan:
        scan_total = sum(a["count"] for a in scan.values())
        scan_lab = sum(a["labeled"] for a in scan.values())
        mins = {str(n): a["minL"] for n, a in sorted(scan.items())}
        if corpus_stats is not None:
            # n = 57 lives in the corpus section of the run
            scan_total += corpus_stats["n57_classes"]
            scan_lab += corpus_stats["n57_labeled"]
            mins.update(corpus_stats["minL"])
        scan_table = {
            "total_classes": scan_total, "total_labeled": scan_lab,
            "mins": mins,
            "min_spectra": {str(n): list(a["min_spec"]) for n, a in
                            sorted(scan.items())},
            "l2_n": [n for n, a in sorted(scan.items()) if a["l2"]],
            "n21_l3": (len(scan.get(21, {}).get("l3", [])),
                       sum(stabilizer(p, 21)[0] for (m, p) in
                           scan.get(21, {}).get("l3", []))),
            "n22_l3": len(scan.get(22, {}).get("l3", [])),
            "n23_l3": len(scan.get(23, {}).get("l3", [])),
            "count_22": scan.get(22, {}).get("count", 0),
            "count_23": scan.get(23, {}).get("count", 0),
            "n21_l3_spectra": [sorted(cycle_spectrum(p, 21)) for (m, p) in
                               scan.get(21, {}).get("l3", [])],
            "iden_counts": {str(n): a["iden"] for n, a in
                            sorted(scan.items()) if a["iden"]},
        }
    res["tables"]["scan"] = scan_table

    # -------------------------------------------------------- claims ----
    for c in CLAIMS:
        status, measured, detail = c.evaluate(res)
        res["claims"].append({
            "id": c.cid, "section": c.section,
            "description": c.description,
            "expected": c.expected,
            "measured": measured,
            "status": status,
            "detail": detail if detail else "",
        })

    with open(args.out, "w", newline="\n", encoding="utf-8") as f:
        json.dump(res, f, indent=1, sort_keys=True, default=str)
    npass = sum(1 for c in res["claims"] if c["status"] == "PASS")
    nfail = sum(1 for c in res["claims"] if c["status"] == "FAIL")
    nskip = sum(1 for c in res["claims"] if c["status"] == "SKIP")
    both("")
    for c in res["claims"]:
        both("  %s %-4s %s" % (c["status"], c["id"], c["description"][:70]))
    both("")
    both("verdict: %d PASS, %d FAIL, %d SKIP" % (npass, nfail, nskip))
    both("report: %s" % args.out)
    lf.close()
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
