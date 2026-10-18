#!/usr/bin/env python3
"""Rebuild Koikoi's continuous activity terrain with Python's standard library."""

import argparse
from array import array
from collections import Counter, deque
from functools import lru_cache
import heapq
import json
import math
from pathlib import Path
import struct
import zlib

PACK = Path(__file__).resolve().parents[1]
SIZE = 1025
ANCHOR = SIZE // 2
SEA_LEVEL = 50
MIN_HEIGHT = 4
MAX_HEIGHT = 256
TARGET_AREA = 180*16*16
ALGORITHM = 'connected-lobes-forest-background-v12'
BIOME_ALGORITHM = 'dappled-without-authored-range-v2'
LAKE_MATERIAL_ALGORITHM = 'lake-sediment-patches-v1'
LAKE_SCALE = math.sqrt(TARGET_AREA / (40 * 16 * 16))
WORLD_SEED = 864242790704001629
# Clockwise from north; these are background land heights, before relief and
# local noise relief. Fourier interpolation avoids octant
# boundaries, while radial attenuation removes the singularity at the center.
DIRECTIONAL_MEANS = (98, 106, 84, 68, 58, 63, 75, 90)
DIRECTION_NAMES = ('N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW')
DIRECTION_HARMONICS = tuple(
    (k, (1 if k == 4 else 2) / 8 * sum(
        h * math.cos(k * i * math.pi / 4) for i, h in enumerate(DIRECTIONAL_MEANS)),
        (1 if k == 4 else 2) / 8 * sum(
        h * math.sin(k * i * math.pi / 4) for i, h in enumerate(DIRECTIONAL_MEANS)))
    for k in range(1, 5))
SURFACE_COLORS = {
    'dappled/lake': (62,114,156),
    'dappled/lake-rocky': (88,107,114),
    'dappled/lake-silt': (121,107,86),
    'dappled/shore': (182,158,99),
    'dappled/activity-golden': (214,172,51),
    'dappled/activity-amber': (211,123,40),
    'dappled/activity-russet': (156,63,40),
    'dappled/activity-emberbark': (191,83,38),
    'temperate/meadows': (113,183,103),
    'mountain/hills': (126,155,141),
    'tundra/forest': (179,200,182),
}


def png(path, rows, bit_depth, color_type):
    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    path.parent.mkdir(parents=True, exist_ok=True)
    header = struct.pack(">IIBBBBB", SIZE, SIZE, bit_depth, color_type, 0, 0, 0)
    raw = b"".join(b"\x00" + row for row in rows)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
                     + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def smoothstep(value):
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


@lru_cache(maxsize=65536)
def lattice(x, z, seed):
    value = (x * 0x9E3779B1 + z * 0x85EBCA77 + seed * 0xC2B2AE3D) & 0xFFFFFFFF
    value ^= value >> 16
    value = (value * 0x7FEB352D) & 0xFFFFFFFF
    value ^= value >> 15
    value = (value * 0x846CA68B) & 0xFFFFFFFF
    value ^= value >> 16
    return value / 0xFFFFFFFF * 2 - 1


def noise(x, z, seed):
    ix, iz = math.floor(x), math.floor(z)
    fx, fz = x - ix, z - iz
    sx = fx * fx * fx * (fx * (fx * 6 - 15) + 10)
    sz = fz * fz * fz * (fz * (fz * 6 - 15) + 10)
    north = lattice(ix, iz, seed) * (1 - sx) + lattice(ix + 1, iz, seed) * sx
    south = lattice(ix, iz + 1, seed) * (1 - sx) + lattice(ix + 1, iz + 1, seed) * sx
    return north * (1 - sz) + south * sz


def fbm(x, z, seed, octaves=3):
    total, amplitude, weight = 0.0, 1.0, 0.0
    for octave in range(octaves):
        total += amplitude * noise(x, z, seed + octave * 1013)
        weight += amplitude
        amplitude *= 0.5
        x, z = x * 2.07 + 11.3, z * 2.07 - 7.1
    return total / weight


def gaussian(x, z, cx, cz, rx, rz):
    return math.exp(-((x - cx) / rx) ** 2 - ((z - cz) / rz) ** 2)


def patch_noise(x, z, seed):
    """A broad Iris-style biome patch field without scanline bands."""
    return .68*fbm(x/82, z/87, seed) + .32*noise(x/29, z/31, seed+97)


def forest_variant(x, z, seed):
    warm = noise(x/67,z/73,seed+787)
    canopy = noise(x/109,z/97,seed+793)
    if warm > .28:
        return 'dappled/activity-golden'
    if warm < -.28:
        return 'dappled/activity-russet'
    return 'dappled/activity-amber' if canopy > 0 else 'dappled/activity-emberbark'


def smootherstep(value):
    value = min(1.0, max(0.0, value))
    return value**3 * (value * (value * 6 - 15) + 10)


def lake_score(x, z, seed):
    """v4017's six rotated lake lobes, enlarged in physical block space."""
    x, z = x / LAKE_SCALE, z / LAKE_SCALE
    wx = x + 19*fbm(x/85, z/85, seed) + 6*noise(x/23, z/23, seed+31)
    wz = z + 18*fbm(x/85, z/85, seed+47) + 6*noise(x/23, z/23, seed+73)
    score = -math.inf
    for cx, cz, rx, rz, angle in [
            (-44,-2,54,37,-.28), (-4,3,46,36,.4), (38,-22,50,27,-.5),
            (22,18,34,35,.65), (43,30,39,30,.45), (-21,34,30,43,-.3)]:
        dx, dz = wx-cx, wz-cz
        u = dx*math.cos(angle) + dz*math.sin(angle)
        v = -dx*math.sin(angle) + dz*math.cos(angle)
        score = max(score, 1-(u/rx)**2-(v/rz)**2)
    score += .18*fbm(x/29,z/29,seed+109)+.07*noise(x/9,z/9,seed+151)
    score -= .85*gaussian(wx,wz,15,32,22,18)
    score -= .70*gaussian(wx,wz,-56,-29,17,15)
    return score


def connected_lake(seed):
    """Expand through cardinal neighbors to preserve one connected lake."""
    wet = bytearray(SIZE*SIZE)
    queued = bytearray(SIZE*SIZE)
    start = ANCHOR*SIZE+ANCHOR
    pending = [(-lake_score(0,0,seed),start)]
    queued[start] = 1
    cutoff = math.inf
    for _ in range(TARGET_AREA):
        score,index = heapq.heappop(pending)
        wet[index] = 1
        cutoff = min(cutoff,-score)
        col,row = index%SIZE,index//SIZE
        if not (32 < col < SIZE-33 and 32 < row < SIZE-33):
            raise ValueError('Lake approaches PNG edge; enlarge SIZE before generation')
        for dx,dz in [(-1,0),(1,0),(0,-1),(0,1)]:
            neighbor = (row+dz)*SIZE+col+dx
            if not queued[neighbor]:
                queued[neighbor] = 1
                value = lake_score(col+dx-ANCHOR,row+dz-ANCHOR,seed)
                heapq.heappush(pending,(-value,neighbor))
    return wet, {'style':'v4017-connected-rotated-lobes','scale':LAKE_SCALE,
                 'cutoff':cutoff,'columns':sum(wet),'rectangularClipping':False}


def squared_distance_line(values):
    """Lower envelope of parabolas: exact squared Euclidean distance in O(n)."""
    n = len(values)
    vertices = [0]*n
    breaks = [-math.inf]+[math.inf]*n
    k = 0
    for q in range(1,n):
        v = vertices[k]
        crossing = ((values[q]+q*q)-(values[v]+v*v))/(2*(q-v))
        while crossing <= breaks[k]:
            k -= 1
            v = vertices[k]
            crossing = ((values[q]+q*q)-(values[v]+v*v))/(2*(q-v))
        k += 1
        vertices[k] = q
        breaks[k] = crossing
        breaks[k+1] = math.inf
    result = array('d',[0])*n
    k = 0
    for q in range(n):
        while breaks[k+1] < q:
            k += 1
        v = vertices[k]
        result[q] = (q-v)**2+values[v]
    return result


def shore_distance(wet, target):
    """Exact distance to opposite land/water pixel centers, in world blocks."""
    infinity = float(SIZE*SIZE*4)
    result = array('d',[0])*len(wet)
    for row in range(SIZE):
        start = row*SIZE
        line = [infinity if wet[start+x] == target else 0 for x in range(SIZE)]
        result[start:start+SIZE] = squared_distance_line(line)
    for col in range(SIZE):
        line = squared_distance_line([result[row*SIZE+col] for row in range(SIZE)])
        for row,value in enumerate(line):
            result[row*SIZE+col] = max(0,math.sqrt(value)-.5)
    return result


def shore_width(x, z, seed):
    # A bounded continuous field, with variation at both bay and grove scales.
    variability = 1.15*noise(x/83,z/79,seed+601)+.45*fbm(x/37,z/43,seed+619)
    return 22.5+7.5*math.tanh(variability)


def directional_mean(x, z):
    """A continuous north-high, south-low background; no eight wedge edges."""
    radius = math.hypot(x, z)
    attenuation = radius / math.sqrt(radius * radius + 70 * 70)
    angle = math.atan2(x, -z)
    return sum(DIRECTIONAL_MEANS) / 8 + sum(
        attenuation ** k * (a * math.cos(k * angle) + c * math.sin(k * angle))
        for k, a, c in DIRECTION_HARMONICS)


def bank_relief(x, z, seed):
    """Smooth hummocks and swales with an authored uplift bounded to 2–6."""
    field = (1.10 * noise(x / 43, z / 47, seed + 967)
             + .45 * fbm(x / 19, z / 23, seed + 977))
    return 4 + 2 * math.tanh(2.5 * field)


def rise_length(x, z, seed):
    """Gradual upland admission; the southern lowland has the gentler ramp."""
    south = .5 + .5 * z / math.sqrt(x*x + z*z + 90*90)
    return 104 + 66 * south + 14 * noise(x / 131, z / 143, seed + 631)


def submerged_profile(x, z, seed):
    """Continuously varying descent scale and curvature; no shared shelf edge."""
    width_field = (.75 * fbm(x / 71, z / 67, seed + 1103)
                   + .75 * noise(x / 37, z / 41, seed + 1117))
    length = 24 + 12 * math.tanh(1.4 * width_field)
    length += 1.5 * (bank_relief(x, z, seed) - 4)
    curvature = 2.35 + .35 * math.tanh(
        1.5 * fbm(x / 53, z / 59, seed + 1129))
    return length, curvature


def submerged_height(x, z, inland, seed):
    """Variable shelves, slopes and hollows connected to the dry-bank field."""
    length, curvature = submerged_profile(x, z, seed)
    bed = 35 + 7 * fbm(x / 55, z / 47, seed + 503)
    bed += 4.5 * fbm(x / 21, z / 19, seed + 521)
    bed += 2 * noise(x / 8, z / 8, seed + 541)
    # The same positive field that raises a bank hummock also raises and
    # widens its submerged continuation. Independent noise supplies hollows.
    bed += 1.35 * (bank_relief(x, z, seed) - 4)
    bed += 3 * fbm(x / 67 + 6, z / 57 - 5, seed + 1141)
    near_water = 49.5 - .45 * math.tanh(inland / 12)
    admission = -math.expm1(-(inland / length) ** curvature)
    bank_scale = 7 + 1.5 * noise(x / 79, z / 83, seed + 983)
    near_admission = -math.expm1(-(inland / bank_scale) ** 2)
    # Continue near-bank curvature into the shallows as well. High bank
    # hummocks retain a shallow toe; adjacent lower banks admit deeper swales.
    toe_drop = (2.4 - .3 * bank_relief(x,z,seed)) * near_admission
    return near_water + admission * (bed - near_water) - (1-admission) * toe_drop


def lake_floor_biome(x, z, water_depth, seed):
    """Broad sediment patches with shared gravel at their material margins."""
    wx = x + 7 * noise(x / 57, z / 51, seed + 1181)
    wz = z + 7 * noise(x / 61, z / 55, seed + 1187)
    rocky = (.75 * noise(wx / 47, wz / 51, seed + 1201)
             + .25 * fbm(wx / 23, wz / 25, seed + 1213))
    silt = (.72 * noise(wx / 59, wz / 63, seed + 1229)
            + .28 * fbm(wx / 31, wz / 29, seed + 1249)
            + .10 * smootherstep((water_depth - 4) / 12))
    if rocky > .24 and rocky > silt + .10:
        return 'dappled/lake-rocky'
    if silt > .28 and silt > rocky + .10:
        return 'dappled/lake-silt'
    return 'dappled/lake'


def activity_biome(x, z, signed, bank_width, seed):
    """Choose a broad, connected activity biome field.

    The lake and its low bank are always dappled-family terrain.  Beyond the
    bank, dappled forest remains the matrix. The existing
    overworld meadow and tundra alternatives are progressively admitted toward the
    outside of the authored area, which avoids a circular biome boundary at a
    fixed distance from the lake.
    """
    if signed < bank_width + 45:
        return forest_variant(x, z, seed)

    climate = fbm(x / 128, z / 117, seed + 871)
    rugged = fbm(x / 52, z / 49, seed + 883)
    meadow_score = .62 * climate + .30 * patch_noise(x, z, seed + 895)
    tundra_score = (-.35 * climate
                    + .35 * fbm(x / 103, z / 111, seed + 907))
    foothill_score = (.36 * rugged
                      + .16 * fbm(x / 170, z / 155, seed + 919))

    # Suppress non-dappled clearings through the activity core, then relax the
    # threshold over a 100-block transition.  This creates broad patches,
    # rather than a hard ring at exactly 150 blocks.
    outer_admission = smootherstep((signed - 95) / 100)
    meadow_threshold = .62 + .30 * (1 - outer_admission)
    tundra_threshold = .66 + .28 * (1 - outer_admission)
    if (meadow_score > meadow_threshold
            and meadow_score > tundra_score + .20
            and meadow_score > foothill_score + .16):
        return 'temperate/meadows'
    if (tundra_score > tundra_threshold
            and tundra_score > meadow_score + .22
            and tundra_score > foothill_score + .16):
        return 'tundra/forest'
    return forest_variant(x, z, seed)


def terrain_height(x, z, signed, seed, bank_width=None):
    """One continuous height expression; signed is physical shoreline distance."""
    if signed < 0:
        return submerged_height(x, z, -signed, seed)
    if bank_width is None:
        bank_width = shore_width(x,z,seed)
    # Iris's overworld combines broad (mountain-large), medium (mountain) and
    # fine (plain/rare-hills) fields.  Keep those scales in the authored
    # height map so the forest does not collapse into one average shelf.
    broad = fbm(x/190, z/170, seed+801)
    medium = fbm(x/74, z/68, seed+811)
    fine = fbm(x/31, z/29, seed+823)
    valley = fbm(x/115 + 17, z/97 - 9, seed+853)
    ridges = noise(x / 59, z / 63, seed + 839)
    upland = directional_mean(x, z) + 15*broad + 11*medium + 4*fine + 5*ridges - 6*valley
    # A soft minimum keeps the authored dry lowlands above water without a
    # flat clipped plateau. Noise remains continuous in the southern lowland.
    upland = 56 + 3 * math.log1p(math.exp((upland - 56) / 3))
    bank_scale = 7 + 1.5 * noise(x / 79, z / 83, seed + 983)
    bank_admission = -math.expm1(-(signed / bank_scale) ** 2)
    bank = 49.5 + .45 * math.tanh(signed / 12) + bank_admission * bank_relief(x,z,seed)
    # This ramp begins continuously at the waterline, without a flat-ring
    # endpoint or one shared outer shelf. The profile varies over world space.
    high_weight = -math.expm1(-(signed / rise_length(x,z,seed)) ** 2.2)
    return bank + high_weight * (upland - bank)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--center-x', type=int, default=0)
    parser.add_argument('--center-z', type=int, default=0)
    parser.add_argument('--layout-seed', type=int)
    args = parser.parse_args()
    current = PACK/'docs/activity-map.json'
    previous = json.loads(current.read_text()) if current.exists() else {}
    seed = args.layout_seed if args.layout_seed is not None else previous.get('layoutSeed')
    if seed is None:
        parser.error('A new layout requires --layout-seed')
    # Regenerate from the declared seed and current parameters every time.
    # Cached outline parameters from another algorithm cannot survive an edit.
    wet,fit = connected_lake(seed)
    print('Connected lake:',fit,flush=True)
    inland = shore_distance(wet,True)
    outside = shore_distance(wet,False)
    print('Physical shoreline distances computed',flush=True)
    heights = array('d')
    terrain = bytearray(SIZE*SIZE)
    local = bytearray(SIZE*SIZE)
    regional = bytearray(SIZE*SIZE)
    surface_rows, lake_rows = [], []
    surface_counts = Counter()
    bank_width_range = [math.inf,-math.inf]
    for row,z in enumerate(range(-ANCHOR,ANCHOR+1)):
        surface_row, lake_row = bytearray(), bytearray()
        for column,x in enumerate(range(-ANCHOR,ANCHOR+1)):
            index = row*SIZE+column
            signed = -inland[index] if wet[index] else outside[index]
            bank_width = shore_width(x,z,seed)
            height = terrain_height(x,z,signed,seed,bank_width)
            assert MIN_HEIGHT < height < MAX_HEIGHT, (x,z,height)
            assert (height < 49.5) == bool(wet[index]), (x,z,height,signed)
            heights.append(height)
            if not wet[index] and signed <= bank_width:
                bank_width_range[0] = min(bank_width_range[0],bank_width)
                bank_width_range[1] = max(bank_width_range[1],bank_width)
            border = smootherstep((ANCHOR-max(abs(x),abs(z)))/48)
            extent = max(0,signed)
            full = 178+18*fbm(x/117,z/90,seed+647)
            fade = 155+20*noise(x/103,z/93,seed+661)
            influence = 1-smootherstep((extent-full)/fade)
            influence *= border
            terrain[index] = round(255*influence)
            forest = (1-smootherstep((extent-170)/90))*border
            regional[index] = round(255*forest)
            local_width = 98+12*noise(x/89,z/81,seed+683)
            local_influence=1-smootherstep((extent-local_width)/110)
            local[index] = round(255*local_influence*border)
            if wet[index]:
                target = lake_floor_biome(x,z,SEA_LEVEL-height,seed)
            elif signed < bank_width:
                target = 'dappled/shore'
            else:
                target = activity_biome(x, z, signed, bank_width, seed)
            surface_row.extend((*SURFACE_COLORS[target], local[index]))
            lake_row.extend((62,114,156,255 if wet[index] else 0))
            if local[index]: surface_counts[target]+=1
        surface_rows.append(bytes(surface_row))
        lake_rows.append(bytes(lake_row))
        if row % 128 == 0:
            print(f'Terrain rows: {row+1}/{SIZE}',flush=True)
    wet_positions = [(i%SIZE-ANCHOR,i//SIZE-ANCHOR) for i,v in enumerate(wet) if v]
    assert abs(len(wet_positions)-TARGET_AREA)<128
    wet_bounds = (min(x for x,z in wet_positions), max(x for x,z in wet_positions),
                  min(z for x,z in wet_positions), max(z for x,z in wet_positions))
    pending, connected = deque([(0,0)]), {(0,0)}
    wet_set = set(wet_positions)
    while pending:
        x,z = pending.popleft()
        for neighbor in [(x-1,z),(x+1,z),(x,z-1),(x,z+1)]:
            if neighbor in wet_set and neighbor not in connected:
                connected.add(neighbor);pending.append(neighbor)
    assert connected==wet_set
    height_rows = [b''.join(struct.pack('>H',round((h-MIN_HEIGHT)/(MAX_HEIGHT-MIN_HEIGHT)*65535))
                           for h in heights[row*SIZE:(row+1)*SIZE]) for row in range(SIZE)]
    png(PACK/'images/activity/lake-height.png',height_rows,16,0)
    png(PACK/'images/activity/terrain-mask.png',[terrain[row*SIZE:(row+1)*SIZE] for row in range(SIZE)],8,0)
    png(PACK/'images/activity/forest-region.png',
        [b''.join(bytes((209,124,41,alpha)) for alpha in regional[row*SIZE:(row+1)*SIZE])
         for row in range(SIZE)],8,6)
    png(PACK/'images/activity/lake-biome.png',lake_rows,8,6)
    png(PACK/'images/activity/surface-biomes.png',surface_rows,8,6)
    placement = {'blocksPerPixel':1,'origin':{'x':args.center_x,'z':args.center_z},
                 'sourceOrigin':{'x':ANCHOR,'z':ANCHOR},'outOfBounds':'FALLBACK'}
    write_json(PACK/'image-maps/activity/lake-height.json',{
        **placement,'source':'activity/lake-height','type':'GRAYSCALE_HEIGHT','sampling':'BILINEAR',
        'alpha':'IGNORE','minimumHeight':MIN_HEIGHT,'maximumHeight':MAX_HEIGHT})
    write_json(PACK/'image-maps/activity/terrain-mask.json',{
        **placement,'source':'activity/terrain-mask','type':'GRAYSCALE_MASK','sampling':'BILINEAR',
        'alpha':'IGNORE','fallbackValue':0})
    for name, colors, fallback in [
        ('forest-region',{'#D17C29':'dappled'},'dappled'),
        ('lake-biome',{'#3E729C':'dappled/lake'},'dappled/lake'),
        ('surface-biomes',{'#'+''.join(f'{v:02X}' for v in rgb):key
                           for key,rgb in SURFACE_COLORS.items()},'dappled/activity-amber')]:
        write_json(PACK/f'image-maps/activity/{name}.json',{
            **placement,'source':f'activity/{name}','type':'COLOR_MAP','sampling':'NEAREST',
            'alpha':'IGNORE','unknownColor':'FALLBACK','fallbackTarget':fallback,'colors':colors})
        write_json(PACK/f'image-maps/activity/{name}-mask.json',{
            **placement,'source':f'activity/{name}','type':'ALPHA_MASK','sampling':'NEAREST',
            'alpha':'IGNORE','fallbackValue':0})
    bounds = {'minX':wet_bounds[0]+args.center_x,
              'maxX':wet_bounds[1]+args.center_x,
              'minZ':wet_bounds[2]+args.center_z,
              'maxZ':wet_bounds[3]+args.center_z}
    bounds.update(width=bounds['maxX']-bounds['minX']+1,length=bounds['maxZ']-bounds['minZ']+1)
    write_json(current,{
        'center':{'x':args.center_x,'z':args.center_z},'waterLevel':SEA_LEVEL,
        'authoredSubmergedColumns':len(wet_positions),'designChunkArea':len(wet_positions)/256,
        'targetChunkArea':TARGET_AREA/256,'rectangularClipping':False,
        'lakeBoundingRectangle':bounds,'layoutSeed':seed,'worldSeed':WORLD_SEED,'terrainAlgorithm':ALGORITHM,
        'biomeAlgorithm':BIOME_ALGORITHM,
        'lakeMaterialAlgorithm':LAKE_MATERIAL_ALGORITHM,
        'naturalOutline':fit,'heightRange':{'min':MIN_HEIGHT,'max':MAX_HEIGHT},
        'authoredHeightRange':[min(heights),max(heights)],
        'shore':'Two-dimensional 2–6 block hummock/swale uplift; continuous bank admission and a direction-dependent exponential rise into independent upland noise.',
        'shoreWidthRange':bank_width_range,
        'shoreReliefRange':[2,6],
        'submergedTransition':'Two-dimensional varying exponential descent scale and curvature; dry-bank noise continues as submerged ridges and shelves; shared waterline height and first derivative.',
        'lakeFloorMaterials':'Existing sand/gravel/dirt/clay background, with coherent stone/andesite/granite/gravel and clay/mud/coarse-dirt sediment patches; all retain minecraft:dappled_forest identity.',
        'directionalUplandMeans':dict(zip(DIRECTION_NAMES,DIRECTIONAL_MEANS)),
        'directionalInterpolation':'Regularized periodic Fourier field; no octant boundaries; north high and south low.',
        'uplandRiseLength':'104 + 66*southness + continuous noise; gentler south-facing lowlands.',
        'northeastMountain':{'enabled':False,'note':'Authored ridge, foothills, biome patch and extended masks removed; original Iris mountains remain reachable.'},
        'terrainMask':'Full influence to roughly 178 shore blocks, then a noise-varying roughly 155-block quintic fade; zero at every image edge.',
        'materials':'Lake, shore and forest retain minecraft:dappled_forest identity; lake-floor block patches retained; all original overworld definitions remain reachable.',
        'surfaceBiomeColumns':dict(surface_counts),
        'note':'Authored estimates only; validate against new saved Minecraft chunks.'})
    print(f'Lake: {len(wet_positions)} columns ({len(wet_positions)/256:.3f} chunk areas); bounds {bounds}',flush=True)


if __name__ == '__main__':
    main()
