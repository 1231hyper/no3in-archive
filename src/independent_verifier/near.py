"""Move 2 / near-neighbor graph (paper Section 6), fresh implementation.

Class-level D4-invariant Hamming distance between classes [S], [T]:

    d_{D4}([S],[T]) = min over g in D4 of |S △ gT|.

The distance-4 certificate is checked structurally: the symmetric
difference is a single alternating C4 (the 2-row column exchange).
"""

from .geom import d4_transforms, images


def _alt_c4_check(s_only, t_only):
    """True iff the two removed points and two added points form one
    alternating C4 (two rows, two columns; S-points in distinct rows)."""
    pts = list(s_only) + list(t_only)
    rows = [r for r, c in pts]
    cols = [c for r, c in pts]
    # each of exactly two rows / two columns occurs exactly twice
    # (note: list * 2 would CONCATENATE, not double each element)
    if sorted(rows) != [x for r in sorted(set(rows)) for x in (r, r)]:
        return False
    if sorted(cols) != [x for c in sorted(set(cols)) for x in (c, c)]:
        return False
    if len(s_only) != 2 or len(t_only) != 2:
        return False
    return s_only[0][0] != s_only[1][0]  # the two removed points in different rows


def near_graph(classes, n, dmax=16):
    """All class pairs with d_{D4} <= dmax.

    Returns (edges, min_dist, dist4_certified, neighbors) where
      edges:      dict {(i, j): min distance} over class pairs
      min_dist:   smallest distance found over ALL pairs examined
                  (all pairs within the candidate filter, which covers
                  every pair with distance <= dmax)
      dist4_certified: number of distance-4 edges that pass the
                  alternating-C4 structural check
      neighbors:  per-class count of neighbors with distance <= dmax
    """
    tr = d4_transforms(n)
    imgs = [images(pts, tr) for pts in classes]
    # inverted index: cell -> [(class_idx, transform_idx)]
    index = {}
    for j, im in enumerate(imgs):
        for g, gpts in enumerate(im):
            for p in gpts:
                index.setdefault(p, []).append((j, g))
    t_threshold = 2 * n - dmax // 2
    edges = {}
    min_dist = None
    min_pair = None
    for i, pts in enumerate(classes):
        counts = {}
        for p in pts:
            for (j, g) in index.get(p, ()):
                if j == i:
                    continue
                key = (j, g)
                counts[key] = counts.get(key, 0) + 1
        for (j, g), c in counts.items():
            if c < t_threshold:
                continue
            dist = 4 * n - 2 * c
            if min_dist is None or dist < min_dist:
                min_dist = dist
                min_pair = (i, j)
            pair = (i, j) if i < j else (j, i)
            if pair not in edges or edges[pair] > dist:
                edges[pair] = dist
    dist4 = 0
    for (i, j), d in edges.items():
        if d == 4:
            # find a transform achieving distance 4 and certify structure
            for g in range(8):
                gt = imgs[j][g]
                s_only = [p for p in classes[i] if p not in gt]
                t_only = [p for p in gt if p not in classes[i]]
                if len(s_only) + len(t_only) == 4 and _alt_c4_check(s_only, t_only):
                    dist4 += 1
                    break
    neighbors = [0] * len(classes)
    for (i, j) in edges:
        neighbors[i] += 1
        neighbors[j] += 1
    return edges, min_dist, dist4, neighbors


def components(edges, size):
    parent = list(range(size))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for (i, j) in edges:
        a, b = find(i), find(j)
        if a != b:
            parent[a] = b
    comp = {}
    for x in range(size):
        comp.setdefault(find(x), []).append(x)
    return sorted((len(v) for v in comp.values()), reverse=True)
