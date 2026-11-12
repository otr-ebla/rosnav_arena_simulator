"""Probe an Isaac Sim environment USD: bounds, floor height, colliders, navmesh bake.

Run inside the container:
    arena_isaac_env; $ISAAC_PATH/python.sh tools/isaac_env_probe.py [Hospital/hospital.usd]
"""
import sys
import functools
print = functools.partial(print, flush=True)  # Isaac exits without flushing stdout

from isaacsim import SimulationApp

app = SimulationApp({"headless": True})

import omni.usd  # noqa: E402
from omni.isaac.core.utils import extensions, stage as stage_utils  # noqa: E402
from omni.isaac.nucleus import get_assets_root_path  # noqa: E402
from pxr import Usd, UsdGeom, UsdPhysics  # noqa: E402

rel = sys.argv[1] if len(sys.argv) > 1 else "Hospital/hospital.usd"
root = get_assets_root_path()
url = f"{root}/Isaac/Environments/{rel}"
print("PROBE assets root:", root)
print("PROBE url:", url)

ok = omni.usd.get_context().open_stage(url)
for _ in range(50):
    app.update()
stage = omni.usd.get_context().get_stage()
print("PROBE open ok:", ok, "upAxis:", UsdGeom.GetStageUpAxis(stage),
      "metersPerUnit:", UsdGeom.GetStageMetersPerUnit(stage))

bbox = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
rng = bbox.ComputeWorldBound(stage.GetPseudoRoot()).ComputeAlignedRange()
print("PROBE bounds min:", rng.GetMin(), "max:", rng.GetMax())

meshes = colliders = 0
for p in stage.Traverse():
    if p.IsA(UsdGeom.Mesh):
        meshes += 1
    if p.HasAPI(UsdPhysics.CollisionAPI):
        colliders += 1
print("PROBE meshes:", meshes, "colliders:", colliders)

print("PROBE top-level:")
for c in stage.GetPseudoRoot().GetChildren():
    print("  ", c.GetPath(), c.GetTypeName())
    for cc in list(c.GetChildren())[:25]:
        print("     ", cc.GetPath(), cc.GetTypeName())

# navmesh bake test
for e in ["omni.anim.navigation.bundle", "omni.anim.navigation.core"]:
    extensions.enable_extension(e)
app.update()
import omni.anim.navigation.core as nav  # noqa: E402
from pxr import Sdf  # noqa: E402

omni.kit.commands.execute("CreateNavMeshVolumeCommand", parent_prim_path=Sdf.Path("/"),
                          layer=stage.GetRootLayer())
app.update()
inav = nav.acquire_interface()
inav.start_navmesh_baking()
for i in range(600):
    app.update()
    nm = inav.get_navmesh()
    if nm is not None:
        print("PROBE navmesh ready after", i, "updates; area count/info:",
              [a for a in dir(nm) if not a.startswith("_")][:20])
        break
else:
    print("PROBE navmesh NOT ready after 600 updates")

app.close()
