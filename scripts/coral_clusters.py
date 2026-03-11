import math
import random

import bpy


COLLECTION_NAME = "Procedural_Coral"
CLUSTER_COUNT = 16
PATCH_AREA_SIZE = 10.0
CLUSTER_SCALE_RANGE = (0.85, 1.3)
PATCH_RANDOM_SEED = None
BEVEL_WIDTH_RANGE = (0.008, 0.02)
SUBSURF_LEVELS = 1
MATERIAL_PALETTES = (
    ((0.86, 0.39, 0.32, 1.0), (0.96, 0.78, 0.56, 1.0)),
    ((0.73, 0.31, 0.52, 1.0), (0.96, 0.67, 0.74, 1.0)),
    ((0.83, 0.52, 0.28, 1.0), (0.95, 0.84, 0.68, 1.0)),
    ((0.58, 0.39, 0.72, 1.0), (0.81, 0.71, 0.9, 1.0)),
)


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


def build_coral_material(name, rng):
    material = bpy.data.materials.new(name=name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    output.location = (520, 0)

    principled = nodes.new(type="ShaderNodeBsdfPrincipled")
    principled.location = (240, 0)
    set_node_input(principled, ("Roughness",), rng.uniform(0.45, 0.72))
    set_node_input(principled, ("Subsurface Weight", "Subsurface"), rng.uniform(0.08, 0.18))
    set_node_input(principled, ("Subsurface Radius",), (1.0, 0.45, 0.35))
    set_node_input(principled, ("Specular IOR Level", "Specular"), rng.uniform(0.28, 0.45))

    coord = nodes.new(type="ShaderNodeTexCoord")
    coord.location = (-980, 0)

    mapping = nodes.new(type="ShaderNodeMapping")
    mapping.location = (-780, 0)
    mapping.inputs["Scale"].default_value = (
        rng.uniform(1.4, 2.3),
        rng.uniform(1.4, 2.3),
        rng.uniform(1.0, 1.6),
    )

    noise = nodes.new(type="ShaderNodeTexNoise")
    noise.location = (-560, 110)
    noise.inputs["Scale"].default_value = rng.uniform(4.0, 7.5)
    noise.inputs["Detail"].default_value = rng.uniform(6.0, 10.0)
    noise.inputs["Roughness"].default_value = 0.58

    voronoi = nodes.new(type="ShaderNodeTexVoronoi")
    voronoi.location = (-560, -120)
    voronoi.feature = "SMOOTH_F1"
    voronoi.inputs["Scale"].default_value = rng.uniform(5.0, 10.0)

    mix_value = nodes.new(type="ShaderNodeMath")
    mix_value.location = (-330, 10)
    mix_value.operation = "MULTIPLY"
    mix_value.inputs[1].default_value = rng.uniform(0.55, 0.9)

    ramp = nodes.new(type="ShaderNodeValToRGB")
    ramp.location = (-100, 20)
    ramp.color_ramp.elements[0].position = 0.28
    ramp.color_ramp.elements[1].position = 0.82
    low_color, high_color = rng.choice(MATERIAL_PALETTES)
    ramp.color_ramp.elements[0].color = low_color
    ramp.color_ramp.elements[1].color = high_color

    bump = nodes.new(type="ShaderNodeBump")
    bump.location = (20, -180)
    bump.inputs["Strength"].default_value = rng.uniform(0.04, 0.12)
    bump.inputs["Distance"].default_value = 0.08

    roughness_ramp = nodes.new(type="ShaderNodeMapRange")
    roughness_ramp.location = (-90, -250)
    roughness_ramp.inputs["To Min"].default_value = rng.uniform(0.35, 0.48)
    roughness_ramp.inputs["To Max"].default_value = rng.uniform(0.68, 0.84)

    links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    links.new(mapping.outputs["Vector"], voronoi.inputs["Vector"])
    links.new(noise.outputs["Fac"], mix_value.inputs[0])
    links.new(voronoi.outputs["Distance"], mix_value.inputs[1])
    links.new(mix_value.outputs["Value"], ramp.inputs["Fac"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(voronoi.outputs["Distance"], roughness_ramp.inputs["Value"])
    links.new(ramp.outputs["Color"], principled.inputs["Base Color"])
    links.new(roughness_ramp.outputs["Result"], principled.inputs["Roughness"])
    links.new(bump.outputs["Normal"], principled.inputs["Normal"])
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    return material


def rotate_point(point, rotation):
    x, y, z = point
    rx, ry, rz = rotation

    cos_x = math.cos(rx)
    sin_x = math.sin(rx)
    y, z = y * cos_x - z * sin_x, y * sin_x + z * cos_x

    cos_y = math.cos(ry)
    sin_y = math.sin(ry)
    x, z = x * cos_y + z * sin_y, -x * sin_y + z * cos_y

    cos_z = math.cos(rz)
    sin_z = math.sin(rz)
    x, y = x * cos_z - y * sin_z, x * sin_z + y * cos_z

    return (x, y, z)


def append_transformed_geometry(vertices, faces, new_vertices, new_faces, offset=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0)):
    base_index = len(vertices)
    ox, oy, oz = offset

    for vertex in new_vertices:
        tx, ty, tz = rotate_point(vertex, rotation)
        vertices.append((tx + ox, ty + oy, tz + oz))

    for face in new_faces:
        faces.append(tuple(base_index + index for index in face))


def make_mound_geometry(radius_x, radius_y, height, sides):
    vertices = [(0.0, 0.0, 0.0)]
    faces = []
    rings = []

    ring_profiles = (
        (1.0, height * 0.12, 0.18),
        (0.88, height * 0.34, 0.12),
        (0.62, height * 0.66, 0.08),
    )

    for scale, z_height, wobble in ring_profiles:
        ring = []
        for index in range(sides):
            angle = (math.tau * index) / sides
            radial_noise = 1.0 + (math.sin(angle * 3.0) * wobble) + (math.cos(angle * 5.0) * wobble * 0.45)
            ring.append(
                (
                    math.cos(angle) * radius_x * scale * radial_noise,
                    math.sin(angle) * radius_y * scale * radial_noise,
                    z_height,
                )
            )
        rings.append(ring)

    ring_starts = []
    for ring in rings:
        ring_starts.append(len(vertices))
        vertices.extend(ring)

    top_index = len(vertices)
    vertices.append((0.0, 0.0, height))

    for index in range(sides):
        next_index = (index + 1) % sides
        faces.append((0, ring_starts[0] + next_index, ring_starts[0] + index))

        for ring_index in range(len(ring_starts) - 1):
            current_start = ring_starts[ring_index]
            next_start = ring_starts[ring_index + 1]
            faces.append(
                (
                    current_start + index,
                    current_start + next_index,
                    next_start + next_index,
                    next_start + index,
                )
            )

        faces.append((ring_starts[-1] + index, ring_starts[-1] + next_index, top_index))

    return vertices, faces


def make_stalk_geometry(
    height,
    base_radius,
    tip_radius,
    sides,
    segments,
    flare=0.0,
    curve_phase=0.0,
    bend=(0.0, 0.0),
    bulge=0.0,
    lip=0.0,
    ripple=0.0,
):
    vertices = []
    faces = []

    for segment in range(segments + 1):
        t = segment / segments
        angle_offset = curve_phase + t * flare
        center_x = bend[0] * (t ** 1.35)
        center_y = bend[1] * (t ** 1.25)
        radius = (base_radius * (1.0 - t)) + (tip_radius * t)
        radius += bulge * math.sin(t * math.pi) ** 2
        radius += lip * max(0.0, t - 0.72) ** 1.3

        for side in range(sides):
            angle = (math.tau * side) / sides + angle_offset
            ripple_scale = 1.0 + (math.sin(angle * 3.0 + curve_phase) * ripple)
            vertices.append(
                (
                    center_x + math.cos(angle) * radius * ripple_scale,
                    center_y + math.sin(angle) * radius * ripple_scale,
                    t * height,
                )
            )

    top_center_index = len(vertices)
    vertices.append((bend[0], bend[1], height))

    for segment in range(segments):
        ring_start = segment * sides
        next_ring_start = (segment + 1) * sides
        for side in range(sides):
            next_side = (side + 1) % sides
            faces.append(
                (
                    ring_start + side,
                    ring_start + next_side,
                    next_ring_start + next_side,
                    next_ring_start + side,
                )
            )

    top_ring_start = segments * sides
    for side in range(sides):
        next_side = (side + 1) % sides
        faces.append((top_ring_start + side, top_ring_start + next_side, top_center_index))

    return vertices, faces


def make_plate_geometry(radius, sides, height):
    vertices = [(0.0, 0.0, 0.0)]
    faces = []

    for index in range(sides):
        angle = (math.tau * index) / sides
        rim_radius = radius * (0.82 + 0.18 * math.sin(angle * 3.0))
        vertices.append((math.cos(angle) * rim_radius, math.sin(angle) * rim_radius, height))

    for index in range(sides):
        next_index = 1 + ((index + 1) % sides)
        faces.append((0, next_index, 1 + index))

    return vertices, faces


def create_coral_cluster_mesh(name, rng):
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    obj = bpy.data.objects.new(name, mesh)

    vertices = []
    faces = []

    mound_vertices, mound_faces = make_mound_geometry(
        radius_x=rng.uniform(0.45, 0.9),
        radius_y=rng.uniform(0.4, 0.85),
        height=rng.uniform(0.22, 0.45),
        sides=rng.randint(9, 12),
    )
    append_transformed_geometry(vertices, faces, mound_vertices, mound_faces)

    finger_count = rng.randint(4, 7)
    for index in range(finger_count):
        angle = (math.tau * index) / finger_count + rng.uniform(-0.4, 0.4)
        distance = rng.uniform(0.05, 0.34)
        offset = (math.cos(angle) * distance, math.sin(angle) * distance, rng.uniform(0.05, 0.12))
        stalk_vertices, stalk_faces = make_stalk_geometry(
            height=rng.uniform(0.55, 1.35),
            base_radius=rng.uniform(0.08, 0.15),
            tip_radius=rng.uniform(0.035, 0.08),
            sides=rng.randint(6, 8),
            segments=rng.randint(4, 5),
            flare=rng.uniform(-0.3, 0.3),
            curve_phase=rng.uniform(0.0, math.tau),
            bend=(rng.uniform(-0.14, 0.14), rng.uniform(-0.14, 0.14)),
            bulge=rng.uniform(0.0, 0.03),
            ripple=rng.uniform(0.01, 0.05),
        )
        append_transformed_geometry(
            vertices,
            faces,
            stalk_vertices,
            stalk_faces,
            offset=offset,
            rotation=(rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12), rng.uniform(0.0, math.tau)),
        )

        if rng.random() < 0.45:
            branch_offset = (
                offset[0] + rng.uniform(-0.06, 0.06),
                offset[1] + rng.uniform(-0.06, 0.06),
                offset[2] + rng.uniform(0.28, 0.62),
            )
            branch_vertices, branch_faces = make_stalk_geometry(
                height=rng.uniform(0.25, 0.6),
                base_radius=rng.uniform(0.03, 0.07),
                tip_radius=rng.uniform(0.015, 0.04),
                sides=rng.randint(5, 7),
                segments=3,
                flare=rng.uniform(-0.22, 0.22),
                curve_phase=rng.uniform(0.0, math.tau),
                bend=(rng.uniform(-0.18, 0.18), rng.uniform(-0.18, 0.18)),
                bulge=rng.uniform(0.0, 0.015),
                ripple=rng.uniform(0.0, 0.04),
            )
            append_transformed_geometry(
                vertices,
                faces,
                branch_vertices,
                branch_faces,
                offset=branch_offset,
                rotation=(rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), rng.uniform(0.0, math.tau)),
            )

    tube_count = rng.randint(3, 5)
    for _ in range(tube_count):
        angle = rng.uniform(0.0, math.tau)
        distance = rng.uniform(0.1, 0.42)
        offset = (math.cos(angle) * distance, math.sin(angle) * distance, rng.uniform(0.04, 0.1))
        stalk_vertices, stalk_faces = make_stalk_geometry(
            height=rng.uniform(0.8, 1.55),
            base_radius=rng.uniform(0.09, 0.17),
            tip_radius=rng.uniform(0.055, 0.11),
            sides=rng.randint(7, 9),
            segments=rng.randint(5, 6),
            flare=rng.uniform(-0.18, 0.18),
            curve_phase=rng.uniform(0.0, math.tau),
            bend=(rng.uniform(-0.09, 0.09), rng.uniform(-0.09, 0.09)),
            bulge=rng.uniform(0.01, 0.04),
            lip=rng.uniform(0.05, 0.14),
            ripple=rng.uniform(0.015, 0.05),
        )
        append_transformed_geometry(
            vertices,
            faces,
            stalk_vertices,
            stalk_faces,
            offset=offset,
            rotation=(rng.uniform(-0.08, 0.08), rng.uniform(-0.08, 0.08), rng.uniform(0.0, math.tau)),
        )

        plate_vertices, plate_faces = make_plate_geometry(
            radius=rng.uniform(0.12, 0.24),
            sides=rng.randint(8, 10),
            height=rng.uniform(0.02, 0.06),
        )
        append_transformed_geometry(
            vertices,
            faces,
            plate_vertices,
            plate_faces,
            offset=(offset[0], offset[1], offset[2] + rng.uniform(0.68, 1.38)),
            rotation=(rng.uniform(-0.2, 0.2), rng.uniform(-0.2, 0.2), rng.uniform(0.0, math.tau)),
        )

    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))

    material = build_coral_material(f"{name}_Material", rng)
    mesh.materials.append(material)

    bevel = obj.modifiers.new(name="Bevel", type="BEVEL")
    bevel.width = rng.uniform(*BEVEL_WIDTH_RANGE)
    bevel.segments = 2
    bevel.limit_method = "ANGLE"

    subsurf = obj.modifiers.new(name="Subdivision", type="SUBSURF")
    subsurf.levels = SUBSURF_LEVELS
    subsurf.render_levels = SUBSURF_LEVELS + 1

    return obj


def build_coral_patch():
    collection = clear_collection_objects(COLLECTION_NAME)
    rng = random.Random(PATCH_RANDOM_SEED)
    half_area = PATCH_AREA_SIZE * 0.5

    for index in range(CLUSTER_COUNT):
        obj = create_coral_cluster_mesh(f"Coral_{index:02d}", rng)
        scale = rng.uniform(*CLUSTER_SCALE_RANGE)

        obj.location = (
            rng.uniform(-half_area, half_area),
            rng.uniform(-half_area, half_area),
            0.0,
        )
        obj.rotation_euler = (
            rng.uniform(-0.06, 0.06),
            rng.uniform(-0.06, 0.06),
            rng.uniform(0.0, math.tau),
        )
        obj.scale = (scale, scale, scale)
        obj["cluster_seed"] = rng.random()

        collection.objects.link(obj)


build_coral_patch()
