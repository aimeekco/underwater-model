import math
import random

import bpy


COLLECTION_NAME = "Procedural_Seaweed"
PATCH_COUNT = 30
PATCH_AREA_SIZE = 10.0
HEIGHT_RANGE = (1.8, 3.4)
WIDTH_RANGE = (0.14, 0.5)
SEGMENT_RANGE = (8, 12)
NOISE_SCALE_RANGE = (0.18, 0.42)
SCALE_RANGE = (0.9, 1.35)
LEAN_RANGE = (-0.06, 0.06)
PATCH_RANDOM_SEED = None
SEAWEED_PALETTES = (
    ((0.08, 0.17, 0.08, 1.0), (0.29, 0.46, 0.17, 1.0)),
    ((0.1, 0.22, 0.12, 1.0), (0.42, 0.57, 0.2, 1.0)),
    ((0.07, 0.16, 0.13, 1.0), (0.26, 0.42, 0.24, 1.0)),
)

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
    owned_materials = []

    for obj in list(collection.objects):
        if obj.type == "MESH" and obj.data is not None:
            owned_meshes.append(obj.data)
            owned_materials.extend(material for material in obj.data.materials if material is not None)
        bpy.data.objects.remove(obj, do_unlink=True)

    for mesh in owned_meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    for material in owned_materials:
        if material.users == 0:
            bpy.data.materials.remove(material)

    return collection


def set_node_input(node, socket_names, value):
    for socket_name in socket_names:
        socket = node.inputs.get(socket_name)
        if socket is not None:
            socket.default_value = value
            return


def build_seaweed_material(name, rng):
    material = bpy.data.materials.new(name=name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    output.location = (620, 0)

    principled = nodes.new(type="ShaderNodeBsdfPrincipled")
    principled.location = (340, 0)
    set_node_input(principled, ("Roughness",), rng.uniform(0.42, 0.62))
    set_node_input(principled, ("Subsurface Weight", "Subsurface"), rng.uniform(0.04, 0.1))
    set_node_input(principled, ("Subsurface Radius",), (0.4, 0.85, 0.2))
    set_node_input(principled, ("Specular IOR Level", "Specular"), rng.uniform(0.22, 0.34))

    coord = nodes.new(type="ShaderNodeTexCoord")
    coord.location = (-1120, 0)

    mapping = nodes.new(type="ShaderNodeMapping")
    mapping.location = (-920, 0)
    mapping.inputs["Scale"].default_value = (
        rng.uniform(1.2, 1.8),
        rng.uniform(1.2, 1.8),
        rng.uniform(0.8, 1.2),
    )

    separate_xyz = nodes.new(type="ShaderNodeSeparateXYZ")
    separate_xyz.location = (-730, -250)

    height_ramp = nodes.new(type="ShaderNodeMapRange")
    height_ramp.location = (-500, -250)
    height_ramp.inputs["From Min"].default_value = -0.2
    height_ramp.inputs["From Max"].default_value = 3.8
    height_ramp.inputs["To Min"].default_value = 0.18
    height_ramp.inputs["To Max"].default_value = 0.95

    wave = nodes.new(type="ShaderNodeTexWave")
    wave.location = (-720, 120)
    wave.wave_type = "BANDS"
    wave.bands_direction = "Z"
    wave.inputs["Scale"].default_value = rng.uniform(5.0, 8.0)
    wave.inputs["Distortion"].default_value = rng.uniform(2.0, 4.5)
    wave.inputs["Detail"].default_value = rng.uniform(3.0, 6.0)
    wave.inputs["Detail Scale"].default_value = 1.6

    noise = nodes.new(type="ShaderNodeTexNoise")
    noise.location = (-720, 320)
    noise.inputs["Scale"].default_value = rng.uniform(4.0, 7.0)
    noise.inputs["Detail"].default_value = rng.uniform(5.0, 8.5)
    noise.inputs["Roughness"].default_value = 0.52

    mix_value = nodes.new(type="ShaderNodeMath")
    mix_value.location = (-500, 120)
    mix_value.operation = "MULTIPLY"

    color_mix = nodes.new(type="ShaderNodeMixRGB")
    color_mix.location = (-270, 20)
    color_mix.blend_type = "MULTIPLY"
    color_mix.inputs["Fac"].default_value = 0.45

    ramp = nodes.new(type="ShaderNodeValToRGB")
    ramp.location = (-40, 20)
    ramp.color_ramp.elements[0].position = 0.18
    ramp.color_ramp.elements[1].position = 0.9
    low_color, high_color = rng.choice(SEAWEED_PALETTES)
    ramp.color_ramp.elements[0].color = low_color
    ramp.color_ramp.elements[1].color = high_color

    bump = nodes.new(type="ShaderNodeBump")
    bump.location = (90, -180)
    bump.inputs["Strength"].default_value = rng.uniform(0.02, 0.06)
    bump.inputs["Distance"].default_value = 0.05

    roughness_ramp = nodes.new(type="ShaderNodeMapRange")
    roughness_ramp.location = (-40, -250)
    roughness_ramp.inputs["To Min"].default_value = rng.uniform(0.32, 0.4)
    roughness_ramp.inputs["To Max"].default_value = rng.uniform(0.58, 0.72)

    links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], wave.inputs["Vector"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    links.new(mapping.outputs["Vector"], separate_xyz.inputs["Vector"])
    links.new(separate_xyz.outputs["Z"], height_ramp.inputs["Value"])
    links.new(wave.outputs["Color"], mix_value.inputs[0])
    links.new(noise.outputs["Fac"], mix_value.inputs[1])
    links.new(height_ramp.outputs["Result"], color_mix.inputs["Color1"])
    links.new(mix_value.outputs["Value"], color_mix.inputs["Color2"])
    links.new(color_mix.outputs["Color"], ramp.inputs["Fac"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(wave.outputs["Color"], roughness_ramp.inputs["Value"])
    links.new(ramp.outputs["Color"], principled.inputs["Base Color"])
    links.new(roughness_ramp.outputs["Result"], principled.inputs["Roughness"])
    links.new(bump.outputs["Normal"], principled.inputs["Normal"])
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    return material


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
        obj.data.materials.append(build_seaweed_material(f"{obj.name}_Material", rng))
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
