import math
import random

import bpy


COLLECTION_NAME = "Procedural_Seaweed"
PATCH_COUNT = 10
PATCH_AREA_SIZE = 5.0
HEIGHT_RANGE = (1.8, 3.4)
WIDTH_RANGE = (0.14, 0.5)
SEGMENT_RANGE = (8, 12)
NOISE_SCALE_RANGE = (0.18, 0.42)
SCALE_RANGE = (0.9, 1.35)
LEAN_RANGE = (-0.06, 0.06)
PATCH_RANDOM_SEED = None

ACTIVE_CURVATURE = {
    "phase": 0.0,
    "twist_turns": 0.6,
    "sweep_frequency": 0.8,
    "helix_radius": 0.06,
    "side_arc": 0.14,
    "forward_arc": 0.09,
    "belly": 0.08,
    "tip_curl_x": 0.0,
    "tip_curl_y": 0.0,
    "taper_power": 1.2,
}


def ensure_collection(name):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    elif bpy.context.scene.collection.children.get(collection.name) is None:
        bpy.context.scene.collection.children.link(collection)
    return collection


def clear_collection_objects(collection_name):
    collection = ensure_collection(collection_name)
    owned_meshes = []

    for obj in list(collection.objects):
        if obj.type == "MESH" and obj.data is not None:
            owned_meshes.append(obj.data)
        bpy.data.objects.remove(obj, do_unlink=True)

    for mesh in owned_meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    return collection


def _centerline_point(t, height, noise_scale):
    z = t * height
    phase = ACTIVE_CURVATURE["phase"]
    twist = ACTIVE_CURVATURE["twist_turns"] * math.tau * t + phase
    sweep = ACTIVE_CURVATURE["sweep_frequency"] * math.pi * t + phase * 0.35
    ribbon_belly = math.sin(math.pi * t) ** 1.15
    tip_zone = max(0.0, t - 0.68) / 0.32

    radius = noise_scale * ACTIVE_CURVATURE["helix_radius"] * (0.2 + 0.55 * t)
    x = math.sin(twist) * radius
    x += math.sin(sweep) * ACTIVE_CURVATURE["side_arc"] * (t ** 1.15)
    x += math.cos(sweep * 0.55 + phase) * ACTIVE_CURVATURE["belly"] * ribbon_belly * 0.4
    x += ACTIVE_CURVATURE["tip_curl_x"] * (tip_zone ** 2.1)

    y = math.cos(twist * 0.72) * radius * 0.8
    y += math.cos(sweep * 0.9) * ACTIVE_CURVATURE["forward_arc"] * (t ** 1.1)
    y += math.sin(sweep * 0.6 - phase) * ACTIVE_CURVATURE["belly"] * ribbon_belly
    y += ACTIVE_CURVATURE["tip_curl_y"] * (tip_zone ** 2.0)
    return x, y, z, twist


def create_seaweed_mesh(name, height, segments, noise_scale, width):
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    obj = bpy.data.objects.new(name, mesh)

    segments = max(2, int(segments))
    vertices = []
    faces = []
    weights = []

    for index in range(segments):
        t = index / (segments - 1)
        center_x, center_y, center_z, twist = _centerline_point(t, height, noise_scale)

        taper = max(0.12, (1.0 - t) ** ACTIVE_CURVATURE["taper_power"])
        half_width = width * 0.5 * taper
        normal_angle = twist + (math.pi * 0.5)
        offset_x = math.cos(normal_angle) * half_width
        offset_y = math.sin(normal_angle) * half_width

        vertices.append((center_x - offset_x, center_y - offset_y, center_z))
        vertices.append((center_x + offset_x, center_y + offset_y, center_z))
        weights.extend((t, t))

    for index in range(segments - 1):
        base = index * 2
        faces.append((base, base + 1, base + 3, base + 2))

    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.polygons.foreach_set("use_smooth", [False] * len(mesh.polygons))

    sway_group = obj.vertex_groups.new(name="Sway_Weight")
    for vertex_index, weight in enumerate(weights):
        sway_group.add([vertex_index], weight, "REPLACE")

    return obj


def build_seaweed_patch():
    collection = clear_collection_objects(COLLECTION_NAME)
    rng = random.Random(PATCH_RANDOM_SEED)
    half_area = PATCH_AREA_SIZE * 0.5

    global ACTIVE_CURVATURE

    for index in range(PATCH_COUNT):
        curve_seed = rng.random()
        dramatic = rng.random()
        height = rng.uniform(*HEIGHT_RANGE)
        segments = rng.randint(*SEGMENT_RANGE)
        noise_scale = rng.uniform(*NOISE_SCALE_RANGE)
        width = rng.uniform(*WIDTH_RANGE)
        scale = rng.uniform(*SCALE_RANGE)
        curl_sign = -1.0 if rng.random() < 0.5 else 1.0

        ACTIVE_CURVATURE = {
            "phase": curve_seed * math.tau,
            "twist_turns": rng.uniform(0.2, 1.1),
            "sweep_frequency": rng.uniform(0.45, 1.1),
            "helix_radius": rng.uniform(0.03, 0.08),
            "side_arc": rng.uniform(0.12, 0.32) * (0.9 + dramatic * 0.4),
            "forward_arc": rng.uniform(0.06, 0.2) * (0.85 + dramatic * 0.35),
            "belly": rng.uniform(0.05, 0.16),
            "tip_curl_x": curl_sign * rng.uniform(0.02, 0.22) * (0.5 + dramatic * 0.7),
            "tip_curl_y": -curl_sign * rng.uniform(0.01, 0.16) * (0.45 + dramatic * 0.6),
            "taper_power": rng.uniform(1.15, 1.85),
        }

        obj = create_seaweed_mesh(
            name=f"Seaweed_{index:02d}",
            height=height,
            segments=segments,
            noise_scale=noise_scale,
            width=width,
        )
        obj["curve_seed"] = curve_seed
        obj["dramatic"] = dramatic

        obj.location = (
            rng.uniform(-half_area, half_area),
            rng.uniform(-half_area, half_area),
            0.0,
        )
        obj.rotation_euler = (
            rng.uniform(*LEAN_RANGE),
            rng.uniform(*LEAN_RANGE),
            rng.uniform(0.0, math.tau),
        )
        obj.scale = (scale, scale, scale)

        collection.objects.link(obj)


build_seaweed_patch()
