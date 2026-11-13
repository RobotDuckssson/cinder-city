# Turn a 4-view "turnaround" GLB into a small game character:
# take the front figure, decimate it by vertex clustering, bake a front/back texture atlas, write a GLB.
import json, struct, io, sys, array, math
from PIL import Image, ImageFilter

src, dst, xcut, target = sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4])
f = open(src, 'rb').read(); clen = struct.unpack('<I', f[12:16])[0]; j = json.loads(f[20:20+clen]); bin0 = f[20+clen+8:]
pr = j['meshes'][0]['primitives'][0]; acc = j['accessors']; bvs = j['bufferViews']
def arr(ai, code):
    a = acc[ai]; bv = bvs[a['bufferView']]; off = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    n = a['count'] * {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3}[a['type']]
    x = array.array(code); x.frombytes(bin0[off:off+n*x.itemsize]); return x
P = arr(pr['attributes']['POSITION'], 'f'); U = arr(pr['attributes']['TEXCOORD_0'], 'f')
I = arr(pr['indices'], {5125: 'I', 5123: 'H'}[acc[pr['indices']]['componentType']])
im = j['images'][0]; bv = bvs[im['bufferView']]
tex = Image.open(io.BytesIO(bin0[bv.get('byteOffset', 0):bv.get('byteOffset', 0)+bv['byteLength']])).convert('RGB')
TW, TH = tex.size; tp = tex.load()

# ---- the front figure: every triangle left of the gap
keep = [P[3*i] < xcut for i in range(len(P)//3)]
tris = [(I[k], I[k+1], I[k+2]) for k in range(0, len(I), 3) if keep[I[k]] and keep[I[k+1]] and keep[I[k+2]]]
used = sorted({v for t in tris for v in t})
xs = [P[3*v] for v in used]; ys = [P[3*v+1] for v in used]; zs = [P[3*v+2] for v in used]
x0, x1, y0, y1, z0, z1 = min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)
Hh = y1 - y0; cx = (x0 + x1) / 2
print('figure verts', len(used), 'tris', len(tris), 'w/h', round((x1-x0)/Hh, 3), 'depth/h', round((z1-z0)/Hh, 3))
# normalised position: feet at y=0, height 1, centred in x; z kept relative to the sheet plane
def npos(v): return ((P[3*v]-cx)/Hh, (P[3*v+1]-y0)/Hh, P[3*v+2]/Hh)
NP = {v: npos(v) for v in used}
hw = (x1 - x0) / Hh / 2 * 1.04   # half width incl. margin
zmin, zmax = z0 / Hh, z1 / Hh

# ---- bake: orthographic front and back views of the full-detail mesh, side by side
VW, VH = 512, 512
def bake(sign):
    img = Image.new('RGB', (VW, VH)); px = img.load(); zb = [[-9.0]*VW for _ in range(VH)]; filled = [[False]*VW for _ in range(VH)]
    def sx(x): return (x*sign + hw) / (2*hw) * VW
    def sy(y): return (1.02 - y) / 1.04 * VH
    for (a, b, c) in tris:
        pa, pb, pc = NP[a], NP[b], NP[c]
        ax, ay, bx, by, cx_, cy = sx(pa[0]), sy(pa[1]), sx(pb[0]), sy(pb[1]), sx(pc[0]), sy(pc[1])
        d = (bx-ax)*(cy-ay) - (cx_-ax)*(by-ay)
        X0 = max(0, int(min(ax, bx, cx_))); X1 = min(VW-1, int(max(ax, bx, cx_)))
        Y0 = max(0, int(min(ay, by, cy))); Y1 = min(VH-1, int(max(ay, by, cy)))
        ua, va, ub, vb, uc, vc = U[2*a], U[2*a+1], U[2*b], U[2*b+1], U[2*c], U[2*c+1]
        for Y in range(Y0, Y1+1):
            for X in range(X0, X1+1):
                qx, qy = X+.5, Y+.5
                if abs(d) < 1e-12: w0 = w1 = w2 = 1/3
                else:
                    w1 = ((qx-ax)*(cy-ay) - (cx_-ax)*(qy-ay)) / d; w2 = ((bx-ax)*(qy-ay) - (qx-ax)*(by-ay)) / d; w0 = 1 - w1 - w2
                    if w0 < -.35 or w1 < -.35 or w2 < -.35: continue   # generous: tiny triangles must still land on a pixel
                    w0 = min(1, max(0, w0)); w1 = min(1, max(0, w1)); w2 = max(0, 1 - w0 - w1)
                z = (w0*pa[2] + w1*pb[2] + w2*pc[2]) * sign
                if z > zb[Y][X]:
                    zb[Y][X] = z; k0 = 1/3 + (w0-1/3)*.7; k1 = 1/3 + (w1-1/3)*.7; k2 = 1 - k0 - k1; u = (k0*ua + k1*ub + k2*uc) % 1; v = (k0*va + k1*vb + k2*vc) % 1   # stay off the island edges of the source atlas
                    px[X, Y] = tp[min(TW-1, int(u*TW)), min(TH-1, int(v*TH))]; filled[Y][X] = True
    # bleed the colours outwards so the silhouette edge never samples black
    for _ in range(10):
        add = []
        for Y in range(VH):
            fr = filled[Y]
            for X in range(VW):
                if fr[X]: continue
                r = g = b = n = 0
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    xx, yy = X+dx, Y+dy
                    if 0 <= xx < VW and 0 <= yy < VH and filled[yy][xx]: c = px[xx, yy]; r += c[0]; g += c[1]; b += c[2]; n += 1
                if n: add.append((X, Y, (r//n, g//n, b//n)))
        for X, Y, c in add: px[X, Y] = c; filled[Y][X] = True
    return img.filter(ImageFilter.MedianFilter(3))
atlas = Image.new('RGB', (2*VW, VH)); atlas.paste(bake(1), (0, 0)); atlas.paste(bake(-1), (VW, 0))
buf = io.BytesIO(); atlas.save(buf, 'JPEG', quality=86); jpg = buf.getvalue()
atlas.save(dst.replace('.glb', '_atlas.jpg'), 'JPEG', quality=90)

# vertices at the same position are one point of the surface, whatever their UVs
_first = {}; WELD = {}
for v in used:
    p = NP[v]; k = (round(p[0]*2e4), round(p[1]*2e4), round(p[2]*2e4)); WELD[v] = _first.setdefault(k, v)
print('welded points', len(_first))
# ---- decimate by vertex clustering; search for the cell size that gives about `target` triangles
def cluster(c):
    # vertices only merge when they share a grid cell AND are connected inside it, so an arm resting
    # against the body (or a hand against a thigh) is never welded to it
    cell = {v: (math.floor(NP[v][0]/c), math.floor(NP[v][1]/c), math.floor(NP[v][2]/c)) for v in used}
    par = dict(WELD)   # start from the position weld: the source mesh is split along its UV seams
    def find(v):
        r = v
        while par[r] != r: r = par[r]
        while par[v] != r: par[v], v = r, par[v]
        return r
    for (a, b, c2) in tris:
        for p, q in ((a, b), (b, c2), (a, c2)):
            if cell[p] == cell[q]:
                rp, rq = find(p), find(q)
                if rp != rq: par[rp] = rq
    cid = {}; sums = []; vmap = {}
    for v in used:
        p = NP[v]; k = find(v)
        i = cid.get(k)
        if i is None: i = cid[k] = len(sums); sums.append([0, 0, 0, 0])
        s = sums[i]; s[0] += p[0]; s[1] += p[1]; s[2] += p[2]; s[3] += 1; vmap[v] = i
    pos = [(s[0]/s[3], s[1]/s[3], s[2]/s[3]) for s in sums]
    out = {}
    for (a, b, c2) in tris:
        A, B, C = vmap[a], vmap[b], vmap[c2]
        if A == B or B == C or A == C: continue
        out.setdefault(tuple(sorted((A, B, C))), (A, B, C))
    return pos, list(out.values())
lo, hi = .004, .06
for _ in range(14):
    mid = (lo + hi) / 2; pos, ft = cluster(mid)
    if len(ft) > target: lo = mid
    else: hi = mid
pos, ft = cluster(hi)
print('cell', round(hi, 4), 'clusters', len(pos), 'tris', len(ft))

# ---- smooth normals per cluster, then split vertices into a front set and a back set for the atlas
nrm = [[0, 0, 0] for _ in pos]; fn = []
for (a, b, c) in ft:
    pa, pb, pc = pos[a], pos[b], pos[c]
    ux, uy, uz = pb[0]-pa[0], pb[1]-pa[1], pb[2]-pa[2]; vx, vy, vz = pc[0]-pa[0], pc[1]-pa[1], pc[2]-pa[2]
    n = (uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx); fn.append(n)
    for i in (a, b, c): nrm[i][0] += n[0]; nrm[i][1] += n[1]; nrm[i][2] += n[2]
def unit(n):
    l = math.sqrt(n[0]*n[0]+n[1]*n[1]+n[2]*n[2]) or 1; return (n[0]/l, n[1]/l, n[2]/l)
nrm = [unit(n) for n in nrm]
vid = {}; VP = []; VN = []; VU = []; idx = []
def vert(i, side):
    k = (i, side); r = vid.get(k)
    if r is None:
        r = vid[k] = len(VP); p = pos[i]; VP.append(p); VN.append(nrm[i])
        sgn = 1 if side == 0 else -1
        u = (p[0]*sgn + hw) / (2*hw); v = (1.02 - p[1]) / 1.04
        u = min(.998, max(.002, u)); VU.append(((u + side) / 2, v))
    return r
for (a, b, c), n in zip(ft, fn):
    side = 0 if n[2] >= 0 else 1
    idx += [vert(a, side), vert(b, side), vert(c, side)]
print('out verts', len(VP), 'tris', len(idx)//3, 'feet lean z', round(sum(p[2] for p in VP if p[1] < .04) / max(1, sum(1 for p in VP if p[1] < .04)) - (zmin+zmax)/2, 4))

# ---- write the GLB
def pad(b, ch=b'\0'): return b + ch * ((4 - len(b) % 4) % 4)
ib = pad(struct.pack('<%dH' % len(idx), *idx)) if len(VP) < 65536 else None
assert ib is not None
vb = b''.join(struct.pack('<8f', *p, *n, *u) for p, n, u in zip(VP, VN, VU))
jp = pad(jpg)
mn = [min(p[k] for p in VP) for k in range(3)]; mx = [max(p[k] for p in VP) for k in range(3)]
g = {"asset": {"version": "2.0", "generator": "cinder-city convert.py"},
     "buffers": [{"byteLength": len(jp)+len(ib)+len(vb)}],
     "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(jpg)},
                     {"buffer": 0, "byteOffset": len(jp), "byteLength": len(idx)*2, "target": 34963},
                     {"buffer": 0, "byteOffset": len(jp)+len(ib), "byteLength": len(vb), "byteStride": 32, "target": 34962}],
     "accessors": [{"type": "SCALAR", "componentType": 5123, "count": len(idx), "bufferView": 1, "byteOffset": 0},
                   {"type": "VEC3", "componentType": 5126, "count": len(VP), "min": mn, "max": mx, "bufferView": 2, "byteOffset": 0},
                   {"type": "VEC3", "componentType": 5126, "count": len(VP), "bufferView": 2, "byteOffset": 12},
                   {"type": "VEC2", "componentType": 5126, "count": len(VP), "bufferView": 2, "byteOffset": 24}],
     "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}],
     "textures": [{"source": 0, "sampler": 0}], "images": [{"mimeType": "image/jpeg", "bufferView": 0}],
     "materials": [{"doubleSided": True, "pbrMetallicRoughness": {"roughnessFactor": .8, "metallicFactor": 0, "baseColorTexture": {"index": 0}}}],
     "meshes": [{"primitives": [{"attributes": {"POSITION": 1, "NORMAL": 2, "TEXCOORD_0": 3}, "mode": 4, "material": 0, "indices": 0}]}],
     "nodes": [{"mesh": 0}], "scenes": [{"nodes": [0]}], "scene": 0}
js = pad(json.dumps(g, separators=(',', ':')).encode(), b' '); body = jp + ib + vb
out = struct.pack('<III', 0x46546C67, 2, 12+8+len(js)+8+len(body)) + struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(body), 0x004E4942) + body
open(dst, 'wb').write(out); print('wrote', dst, len(out))
