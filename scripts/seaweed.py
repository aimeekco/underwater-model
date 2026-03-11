import math
import random

import bpy


COLLECTION_NAME = "Procedural_Seaweed"
PATCH_COUNT = 10
PATCH_AREA_SIZE = 5.0
HEIGHT_RANGE = (1.2, 2.8)
WIDTH_RANGE = (0.08, 0.22)
SEGMENT_RANGE = (8, 12)
NOISE_SCALE_RANGE = (0.15, 0.5)
SCALE_RANGE = (0.85, 1.3)
LEAN_RANGE = (-0.2, 0.2)
PATCH_RANDOM_SEED = None

ACTIVE_CURVATURE_SEED = 0.0


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
    phase = ACTIVE_CURVATURE_SEED * math.tau
    twist = (1.2 + noise_scale * 1.8) * math.tau * t + phase
    sway = (0.7 + noise_scale * 0.9) * math.pi * t + phase * 0.5

    radius = noise_scale * (0.12 + 0.18 * t)
    x = math.sin(twist) * radius + math.cos(sway) * noise_scale * 0.08 * t
    y = math.cos(twist * 0.85) * radius + math.sin(sway * 1.3) * noise_scale * 0.1 * t
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

        taper = max(0.08, 1.0 - t)
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

    global ACTIVE_CURVATURE_SEED

    for index in range(PATCH_COUNT):
        ACTIVE_CURVATURE_SEED = rng.random()
        height = rng.uniform(*HEIGHT_RANGE)
        segments = rng.randint(*SEGMENT_RANGE)
        noise_scale = rng.uniform(*NOISE_SCALE_RANGE)
        width = rng.uniform(*WIDTH_RANGE)
        scale = rng.uniform(*SCALE_RANGE)

        obj = create_seaweed_mesh(
            name=f"Seaweed_{index:02d}",
            height=height,
            segments=segments,
            noise_scale=noise_scale,
            width=width,
        )
        obj["curve_seed"] = ACTIVE_CURVATURE_SEED

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
