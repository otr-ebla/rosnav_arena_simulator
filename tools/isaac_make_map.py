"""Generate an Arena/Nav2 2D occupancy map from an Isaac Sim environment USD.

The map is in Isaac's world frame (Arena's map frame == Isaac world frame), so
the robot, pedestrians and Nav2 line up with the 3D scene.

Inside the container:
    arena_isaac_env
    $ISAAC_PATH/python.sh tools/isaac_make_map.py Hospital/hospital.usd \
        arena4_ws/src/arena/simulation-setup/worlds/isaac_hospital/map [--origin X Y]

Cells: occupied = any collider between floor+ZMIN and floor+ZMAX; free = cells the
generator reaches from the origin; everything else (outside, closed rooms) is
written as occupied, because Arena treats unknown cells as free spawn space.
"""
import argparse
import functools
import os
import sys

print = functools.partial(print, flush=True)  # Isaac exits without flushing stdout

ap = argparse.ArgumentParser()
ap.add_argument("usd", help="path below <assets>/Isaac/Environments, or a full URL/path")
ap.add_argument("out_dir")
ap.add_argument("--res", type=float, default=0.05, help="cell size [m]")
ap.add_argument("--zmin", type=float, default=0.10, help="slice bottom above floor [m]")
ap.add_argument("--zmax", type=float, default=1.80, help="slice top above floor [m]")
ap.add_argument("--clearance", type=float, default=0.30,
                help="robot radius [m]: areas reachable only through narrower gaps become occupied")
ap.add_argument("--origin", type=float, nargs=2, default=None,
                help="a free point (x y) to start from; default: navmesh point near the scene centre")
args = ap.parse_args()

from isaacsim import SimulationApp  # noqa: E402

app = SimulationApp({"headless": True})

import numpy as np  # noqa: E402
from scipy import ndimage  # noqa: E402
import omni.kit.commands  # noqa: E402
import omni.usd  # noqa: E402
from omni.isaac.core import SimulationContext  # noqa: E402
from omni.isaac.core.utils import extensions  # noqa: E402
from omni.isaac.nucleus import get_assets_root_path  # noqa: E402
from pxr import Sdf, Usd, UsdGeom  # noqa: E402

url = args.usd if ("://" in args.usd or os.path.isabs(args.usd)) else \
    f"{get_assets_root_path()}/Isaac/Environments/{args.usd}"
print("MAP loading", url)
omni.usd.get_context().open_stage(url)
for _ in range(30):
    app.update()
stage = omni.usd.get_context().get_stage()

bbox = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
rng = bbox.ComputeWorldBound(stage.GetPseudoRoot()).ComputeAlignedRange()
bmin, bmax = rng.GetMin(), rng.GetMax()
print("MAP bounds", bmin, bmax)

# navmesh: floor height and a free start point
for e in ["omni.anim.navigation.bundle", "omni.anim.navigation.core", "omni.isaac.occupancy_map"]:
    extensions.enable_extension(e)
app.update()
import omni.anim.navigation.core as nav  # noqa: E402
from omni.isaac.occupancy_map.bindings import _occupancy_map  # noqa: E402

omni.kit.commands.execute("CreateNavMeshVolumeCommand", parent_prim_path=Sdf.Path("/"),
                          layer=stage.GetRootLayer())
app.update()
inav = nav.acquire_interface()
inav.start_navmesh_baking()
navmesh = None
for _ in range(1200):
    app.update()
    navmesh = inav.get_navmesh()
    if navmesh is not None:
        break
if navmesh is None:
    sys.exit("navmesh did not bake")

centre = [(bmin[0] + bmax[0]) / 2, (bmin[1] + bmax[1]) / 2, 0.0]
if args.origin:
    centre = [args.origin[0], args.origin[1], 0.0]
import carb  # noqa: E402

out = carb.Float3(0.0, 0.0, 0.0)
navmesh.query_closest_point(carb.Float3(*centre), out)
p = [out.x, out.y, out.z]
floor_z = float(p[2])
print(f"MAP start point {p}  floor z {floor_z:.3f}")

# Give every visible mesh a collider (in a throw-away session sublayer), like
# the occupancy map UI does with "Use PhysX Collision Geometry" off: some scene
# parts (railings, small furniture) have no collider but the RTX lidar sees them.
from omni.physx.scripts import utils as physx_utils  # noqa: E402
from pxr import UsdPhysics  # noqa: E402

layer = Sdf.Layer.CreateAnonymous("wm_occupancy_colliders")
stage.GetSessionLayer().subLayerPaths.append(layer.identifier)
added = 0
with Usd.EditContext(stage, layer):
    with Sdf.ChangeBlock():
        for prim in stage.Traverse():
            im = UsdGeom.Imageable(prim)
            if im and im.ComputeVisibility(Usd.TimeCode.Default()) == UsdGeom.Tokens.invisible:
                continue
            if prim.HasAPI(UsdPhysics.CollisionAPI):
                continue
            if prim.IsA(UsdGeom.Mesh):
                pts = UsdGeom.Mesh(prim).GetPointsAttr().Get()
                if not pts:
                    continue
            if (prim.IsA(UsdGeom.Xformable) and prim.IsInstanceable()) or prim.IsA(UsdGeom.Gprim):
                UsdPhysics.CollisionAPI.Apply(prim)
                UsdPhysics.MeshCollisionAPI.Apply(prim).CreateApproximationAttr().Set("none")
                added += 1
for _ in range(5):
    app.update()
print(f"MAP colliders added for occupancy: {added}")

# occupancy map (physics must be running)
sim = SimulationContext(stage_units_in_meters=1.0)
sim.play()
for _ in range(5):
    app.update()
om = _occupancy_map.acquire_occupancy_map_interface()
om.set_cell_size(args.res)


def generate(z0, z1):
    om.set_transform((p[0], p[1], floor_z),
                     (bmin[0] - p[0], bmin[1] - p[1], z0),
                     (bmax[0] - p[0], bmax[1] - p[1], z1))
    om.update()
    om.generate()
    app.update()
    return (np.array(om.get_occupied_positions(), dtype=float).reshape(-1, 3),
            np.array(om.get_free_positions(), dtype=float).reshape(-1, 3))


occ, free = generate(args.zmin, args.zmax)
# floor check: a thin slice through the floor; cells with nothing there are
# holes (stairs going down, openings) and must not be driven into
floor_cells, _ = generate(-0.06, 0.02)
sim.stop()
print(f"MAP occupied cells {len(occ)}, free cells {len(free)}, floor cells {len(floor_cells)}")
if len(free) == 0:
    sys.exit("no free cells: start point not in free space? use --origin X Y")

# rasterise into a ROS map image (row 0 = top = max y)
x0 = float(np.floor(bmin[0] / args.res) * args.res)
y0 = float(np.floor(bmin[1] / args.res) * args.res)
w = int(np.ceil((bmax[0] - x0) / args.res)) + 1
h = int(np.ceil((bmax[1] - y0) / args.res)) + 1
img = np.zeros((h, w), dtype=np.uint8)  # 0 = occupied (also: outside / unreachable)


def cells(pts):
    ix = np.floor((pts[:, 0] - x0) / args.res).astype(int)
    iy = np.floor((pts[:, 1] - y0) / args.res).astype(int)
    ok = (ix >= 0) & (ix < w) & (iy >= 0) & (iy < h)
    return h - 1 - iy[ok], ix[ok]


img[cells(free)] = 254
img[cells(occ)] = 0
has_floor = np.zeros_like(img, dtype=bool)
has_floor[cells(floor_cells)] = True
has_floor = ndimage.binary_closing(has_floor, iterations=2)  # tiny gaps between floor tiles
img[~has_floor] = 0

# keep only the free area connected to the start point (the generator marks
# everything inside the bounds as free, including outside the building).
# Flood fill over free cells with the obstacles grown by one cell, so that
# 1-cell diagonal gaps between wall pieces do not leak.
free_mask = img == 254
# Obstacles are grown by the robot clearance for the flood fill, so pockets
# that connect to the rest only through gaps narrower than the robot (stair
# landings behind railings, between furniture) do not count as reachable:
# Arena picks robot spawns and goals from the free cells.
grow = max(1, int(round(args.clearance / args.res)))
disk = ndimage.generate_binary_structure(2, 1)
closed = free_mask & ~ndimage.binary_dilation(~free_mask, structure=disk, iterations=grow)
labels, _ = ndimage.label(closed)  # 4-connectivity
sr, sc = cells(np.array([[p[0], p[1], 0.0]]))
seed = labels[sr[0], sc[0]]
if seed == 0:
    sys.exit("start point has less than --clearance to obstacles; use --origin X Y")
reach = ndimage.binary_dilation(labels == seed, structure=disk, iterations=grow) & free_mask
img[:] = 0
img[reach] = 254

os.makedirs(args.out_dir, exist_ok=True)
with open(os.path.join(args.out_dir, "map.pgm"), "wb") as f:
    f.write(f"P5\n# generated by tools/isaac_make_map.py from {url}\n{w} {h}\n255\n".encode())
    f.write(img.tobytes())
with open(os.path.join(args.out_dir, "map.yaml"), "w") as f:
    f.write("image: map.pgm\nresolution: %g\norigin: [%.3f, %.3f, 0.0]\n"
            "negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n" % (args.res, x0, y0))
print(f"MAP wrote {args.out_dir}/map.pgm {w}x{h} origin ({x0:.3f}, {y0:.3f}) "
      f"free {100.0 * (img == 254).mean():.1f}%  floor_z {floor_z:.3f}")
app.close()
