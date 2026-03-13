import importlib
import importlib.util
import math
import random
import sys
import types
from pathlib import Path

import bpy


def _candidate_module_dirs():
    candidates = []

    if "__file__" in globals():
        this_file = Path(__file__).resolve()
        candidates.append(this_file.parent)
        candidates.append(this_file.parent / "scripts")

    cwd = Path.cwd()
    candidates.append(cwd)
    candidates.append(cwd / "scripts")
    candidates.append(Path.home() / "underwater-model")
    candidates.append(Path.home() / "underwater-model" / "scripts")

    blend_dir = Path(bpy.path.abspath("//")).resolve()
    candidates.append(blend_dir)
    candidates.append(blend_dir / "scripts")

    deduped = []
    seen = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _load_module(module_name, filename):
    for target in (module_name, f"scripts.{module_name}"):
        try:
            return importlib.import_module(target)
        except ImportError:
            pass

    for module_dir in _candidate_module_dirs():
        module_path = module_dir / filename
        if not module_path.exists():
            continue

        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            continue

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    for text_name in (filename, module_name, f"{module_name}.py"):
        text_block = bpy.data.texts.get(text_name)
        if text_block is None:
            continue

        module = types.ModuleType(module_name)
        sys.modules[module_name] = module
        exec(text_block.as_string(), module.__dict__)
        return module

    raise ImportError(f"Unable to load module '{module_name}' ({filename}) from known filesystem or Blender text locations.")


CoralGenerator = _load_module("coral_clusters", "coral_clusters.py").CoralGenerator
SeaweedGenerator = _load_module("seaweed", "seaweed.py").SeaweedGenerator


WORLD_COLLECTION_NAME = "FishStack_World"
SECTOR_DEFINITIONS = (
    ("Left", -30.0),
    ("Forward", 0.0),
    ("Right", 30.0),
)
GHOST_BOID_SECTORS = ("Forward", "Right")


def ensure_collection(name, parent=None):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)

    if parent is None:
        if bpy.context.scene.collection.children.get(collection.name) is None:
            bpy.context.scene.collection.children.link(collection)
    else:
        if parent.children.get(collection.name) is None:
            parent.children.link(collection)

    return collection


def _remove_child_collections(parent_collection):
    for child in list(parent_collection.children):
        _remove_child_collections(child)
        parent_collection.children.unlink(child)
        if child.users == 0:
            bpy.data.collections.remove(child)


def clear_collection_objects(collection):
    owned_meshes = []
    owned_materials = []
    removed_object_names = set()

    def remove_objects_recursive(target_collection):
        for obj in list(target_collection.objects):
            if obj.name in removed_object_names:
                continue

            removed_object_names.add(obj.name)
            if obj.type == "MESH" and obj.data is not None:
                if obj.data not in owned_meshes:
                    owned_meshes.append(obj.data)
                for material in obj.data.materials:
                    if material is not None:
                        if material not in owned_materials:
                            owned_materials.append(material)
            bpy.data.objects.remove(obj, do_unlink=True)

        for child in target_collection.children:
            remove_objects_recursive(child)

    remove_objects_recursive(collection)
    _remove_child_collections(collection)

    for mesh in owned_meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    for material in owned_materials:
        if material.users == 0:
            bpy.data.materials.remove(material)


def _create_cube_mesh(name, size=2.0):
    half_size = size * 0.5
    vertices = [
        (-half_size, -half_size, -half_size),
        (half_size, -half_size, -half_size),
        (half_size, half_size, -half_size),
        (-half_size, half_size, -half_size),
        (-half_size, -half_size, half_size),
        (half_size, -half_size, half_size),
        (half_size, half_size, half_size),
        (-half_size, half_size, half_size),
    ]
    faces = [
        (0, 1, 2, 3),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    ]

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.polygons.foreach_set("use_smooth", [False] * len(mesh.polygons))
    return mesh


def spawn_ruin_placeholders(collection, left_sector_center):
    ruin_mesh = _create_cube_mesh("Ruin_CRT_Placeholder", size=2.4)
    ruin_obj = bpy.data.objects.new("Ruin_CRT_Placeholder", ruin_mesh)
    ruin_obj.location = (left_sector_center[0], left_sector_center[1], left_sector_center[2] + 1.2)
    collection.objects.link(ruin_obj)
    return ruin_obj


def _create_ghost_fish_mesh(name):
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    vertices = [
        (0.0, 0.42, 0.0),
        (-0.17, -0.08, 0.11),
        (0.17, -0.08, 0.11),
        (0.17, -0.08, -0.11),
        (-0.17, -0.08, -0.11),
        (0.0, -0.42, 0.0),
    ]
    faces = [
        (0, 1, 2),
        (0, 2, 3),
        (0, 3, 4),
        (0, 4, 1),
        (5, 2, 1),
        (5, 3, 2),
        (5, 4, 3),
        (5, 1, 4),
    ]
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.polygons.foreach_set("use_smooth", [False] * len(mesh.polygons))
    return mesh


def _limit_vector(vec, max_length):
    x, y, z = vec
    length = math.sqrt((x * x) + (y * y) + (z * z))
    if length <= max_length or length == 0.0:
        return vec
    scale = max_length / length
    return (x * scale, y * scale, z * scale)


def spawn_ghost_boids(
    collection,
    rng,
    sector_center,
    name_prefix="GhostFish",
    count=30,
    area_size=10.0,
    frame_start=1,
    frame_end=240,
    frame_step=8,
):
    boids = []
    half_area = area_size * 0.5
    scene = bpy.context.scene
    scene.frame_start = frame_start
    scene.frame_end = max(scene.frame_end, frame_end)
    scene.frame_preview_start = frame_start
    scene.frame_preview_end = frame_end

    for index in range(count):
        obj_name = f"{name_prefix}_{index:02d}"
        mesh = _create_ghost_fish_mesh(obj_name)
        obj = bpy.data.objects.new(obj_name, mesh)
        collection.objects.link(obj)

        position = [
            sector_center[0] + rng.uniform(-half_area, half_area),
            sector_center[1] + rng.uniform(-half_area, half_area),
            sector_center[2] + rng.uniform(0.6, 3.4),
        ]
        velocity = [
            rng.uniform(-0.14, 0.14),
            rng.uniform(0.28, 0.62),
            rng.uniform(-0.07, 0.07),
        ]
        boid_scale = rng.uniform(0.35, 0.9)
        obj.scale = (boid_scale, boid_scale, boid_scale)
        boids.append({"obj": obj, "position": position, "velocity": velocity})

    neighbor_radius = 3.4
    separation_weight = 0.1
    alignment_weight = 0.075
    cohesion_weight = 0.05
    jitter_weight = 0.055
    boundary_weight = 0.18
    max_speed = 0.95

    for boid in boids:
        obj = boid["obj"]
        velocity = boid["velocity"]
        obj.location = tuple(boid["position"])
        heading_xy = math.atan2(velocity[1], velocity[0]) - (math.pi * 0.5)
        pitch = math.atan2(velocity[2], max(0.001, math.sqrt((velocity[0] * velocity[0]) + (velocity[1] * velocity[1]))))
        obj.rotation_euler = (pitch, 0.0, heading_xy)
        obj.hide_viewport = False
        obj.hide_render = False
        obj.keyframe_insert(data_path="location", frame=frame_start)
        obj.keyframe_insert(data_path="rotation_euler", frame=frame_start)
        obj.keyframe_insert(data_path="hide_viewport", frame=frame_start)
        obj.keyframe_insert(data_path="hide_render", frame=frame_start)

    for frame in range(frame_start + frame_step, frame_end + 1, frame_step):
        for boid in boids:
            position = boid["position"]
            velocity = boid["velocity"]

            neighbors = []
            for other in boids:
                if other is boid:
                    continue
                dx = other["position"][0] - position[0]
                dy = other["position"][1] - position[1]
                dz = other["position"][2] - position[2]
                distance = math.sqrt((dx * dx) + (dy * dy) + (dz * dz))
                if distance < neighbor_radius:
                    neighbors.append((other, distance, dx, dy, dz))

            sep = [0.0, 0.0, 0.0]
            ali = [0.0, 0.0, 0.0]
            coh = [0.0, 0.0, 0.0]

            if neighbors:
                for neighbor, distance, dx, dy, dz in neighbors:
                    inv = 1.0 / max(distance, 0.0001)
                    sep[0] -= dx * inv
                    sep[1] -= dy * inv
                    sep[2] -= dz * inv
                    ali[0] += neighbor["velocity"][0]
                    ali[1] += neighbor["velocity"][1]
                    ali[2] += neighbor["velocity"][2]
                    coh[0] += neighbor["position"][0]
                    coh[1] += neighbor["position"][1]
                    coh[2] += neighbor["position"][2]

                count_inv = 1.0 / len(neighbors)
                ali[0] = (ali[0] * count_inv) - velocity[0]
                ali[1] = (ali[1] * count_inv) - velocity[1]
                ali[2] = (ali[2] * count_inv) - velocity[2]
                coh[0] = (coh[0] * count_inv) - position[0]
                coh[1] = (coh[1] * count_inv) - position[1]
                coh[2] = (coh[2] * count_inv) - position[2]

            jitter = [
                rng.uniform(-1.0, 1.0),
                rng.uniform(-1.0, 1.0),
                rng.uniform(-0.6, 0.6),
            ]

            boundary = [
                sector_center[0] - position[0],
                sector_center[1] - position[1],
                (sector_center[2] + 1.8) - position[2],
            ]

            velocity[0] += (
                (sep[0] * separation_weight)
                + (ali[0] * alignment_weight)
                + (coh[0] * cohesion_weight)
                + (jitter[0] * jitter_weight)
                + (boundary[0] * boundary_weight * 0.015)
            )
            velocity[1] += (
                (sep[1] * separation_weight)
                + (ali[1] * alignment_weight)
                + (coh[1] * cohesion_weight)
                + (jitter[1] * jitter_weight)
                + (boundary[1] * boundary_weight * 0.015)
                + 0.045
            )
            velocity[2] += (
                (sep[2] * separation_weight)
                + (ali[2] * alignment_weight)
                + (coh[2] * cohesion_weight)
                + (jitter[2] * jitter_weight)
                + (boundary[2] * boundary_weight * 0.015)
            )

            velocity[:] = _limit_vector(velocity, max_speed)
            position[0] += velocity[0]
            position[1] += velocity[1]
            position[2] = min(max(sector_center[2] + 0.4, position[2] + velocity[2]), sector_center[2] + 4.2)

            if abs(position[0] - sector_center[0]) > half_area:
                position[0] = sector_center[0] + rng.uniform(-half_area * 0.9, half_area * 0.9)
            if abs(position[1] - sector_center[1]) > half_area:
                position[1] = sector_center[1] + rng.uniform(-half_area * 0.9, half_area * 0.9)

            obj = boid["obj"]
            obj.location = (position[0], position[1], position[2])

            heading_xy = math.atan2(velocity[1], velocity[0]) - (math.pi * 0.5)
            pitch = math.atan2(velocity[2], max(0.001, math.sqrt((velocity[0] * velocity[0]) + (velocity[1] * velocity[1]))))
            obj.rotation_euler = (pitch, 0.0, heading_xy)

            obj.keyframe_insert(data_path="location", frame=frame)
            obj.keyframe_insert(data_path="rotation_euler", frame=frame)

            is_hidden = rng.random() < 0.08
            obj.hide_viewport = is_hidden
            obj.hide_render = is_hidden
            obj.keyframe_insert(data_path="hide_viewport", frame=frame)
            obj.keyframe_insert(data_path="hide_render", frame=frame)

    for boid in boids:
        action = boid["obj"].animation_data.action if boid["obj"].animation_data else None
        if action is None:
            continue
        fcurves = getattr(action, "fcurves", None)
        if fcurves is None:
            # Blender's newer animation data model may not expose Action.fcurves.
            # Keyframes are still valid; we simply skip interpolation overrides.
            continue
        for fcurve in fcurves:
            data_path = getattr(fcurve, "data_path", "")
            keyframe_points = getattr(fcurve, "keyframe_points", ())
            if data_path in {"location", "rotation_euler"}:
                for key in keyframe_points:
                    key.interpolation = "LINEAR"
            elif data_path in {"hide_viewport", "hide_render"}:
                for key in keyframe_points:
                    key.interpolation = "CONSTANT"

    return [boid["obj"] for boid in boids]


def generate_world(seed):
    world_collection = ensure_collection(WORLD_COLLECTION_NAME)
    clear_collection_objects(world_collection)

    seaweed_generator = SeaweedGenerator()
    coral_generator = CoralGenerator()
    world_rng = random.Random(seed)

    sector_centers = {}
    for sector_name, x_offset in SECTOR_DEFINITIONS:
        sector_collection = ensure_collection(f"Sector_{sector_name}", parent=world_collection)
        sector_center = (x_offset, 0.0, 0.0)
        sector_centers[sector_name] = sector_center

        seaweed_seed = world_rng.randint(0, 10**9)
        coral_seed = world_rng.randint(0, 10**9)
        seaweed_generator.build_patch(collection=sector_collection, seed=seaweed_seed, origin=sector_center)
        coral_generator.build_patch(collection=sector_collection, seed=coral_seed, origin=sector_center)
        if sector_name in GHOST_BOID_SECTORS:
            boid_seed = world_rng.randint(0, 10**9)
            boid_rng = random.Random(boid_seed)
            spawn_ghost_boids(
                collection=sector_collection,
                rng=boid_rng,
                sector_center=sector_center,
                name_prefix=f"{sector_name}_GhostFish",
                count=30,
                area_size=12.0,
            )

    spawn_ruin_placeholders(world_collection, sector_centers["Left"])
    return world_collection
