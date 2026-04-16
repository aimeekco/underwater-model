import math
import random

import bpy


class UrchinGenerator:
    URCHIN_PALETTES = (
        ((0.16, 0.11, 0.09, 1.0), (0.46, 0.35, 0.26, 1.0)),
        ((0.14, 0.18, 0.12, 1.0), (0.4, 0.52, 0.24, 1.0)),
        ((0.12, 0.14, 0.18, 1.0), (0.34, 0.42, 0.56, 1.0)),
    )

    CORRUPTED_DIRECTIONS = (
        (1.0, 0.0, 0.0),
        (-1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, -1.0, 0.0),
        (0.0, 0.0, 1.0),
        (0.71, 0.71, 0.0),
        (-0.71, 0.71, 0.0),
        (0.71, -0.71, 0.0),
        (0.0, 0.71, 0.71),
        (0.0, -0.71, 0.71),
        (0.71, 0.0, 0.71),
        (-0.71, 0.0, 0.71),
    )

    def __init__(
        self,
        patch_count=80,
        patch_area_size=80.0,
        scale_range=(0.55, 1.2),
        snap_increment=0.06,
        bevel_width_range=(0.004, 0.012),
    ):
        self.patch_count = patch_count
        self.patch_area_size = patch_area_size
        self.scale_range = scale_range
        self.snap_increment = snap_increment
        self.bevel_width_range = bevel_width_range

    @staticmethod
    def _set_node_input(node, socket_names, value):
        for socket_name in socket_names:
            socket = node.inputs.get(socket_name)
            if socket is not None:
                socket.default_value = value
                return

    @staticmethod
    def _lerp(a, b, t):
        return a + ((b - a) * t)

    def _snap_lerp(self, value, amount):
        if self.snap_increment <= 0.0:
            return value
        snapped = round(value / self.snap_increment) * self.snap_increment
        return self._lerp(value, snapped, amount)

    def _build_urchin_material(self, name, rng):
        material = bpy.data.materials.new(name=name)
        material.use_nodes = True
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        nodes.clear()

        output = nodes.new(type="ShaderNodeOutputMaterial")
        output.location = (520, 0)

        principled = nodes.new(type="ShaderNodeBsdfPrincipled")
        principled.location = (240, 0)
        self._set_node_input(principled, ("Roughness",), rng.uniform(0.36, 0.58))
        self._set_node_input(principled, ("Subsurface Weight", "Subsurface"), rng.uniform(0.0, 0.04))
        self._set_node_input(principled, ("Specular IOR Level", "Specular"), rng.uniform(0.3, 0.48))

        coord = nodes.new(type="ShaderNodeTexCoord")
        coord.location = (-920, 0)

        mapping = nodes.new(type="ShaderNodeMapping")
        mapping.location = (-720, 0)
        mapping.inputs["Scale"].default_value = (
            rng.uniform(1.2, 1.9),
            rng.uniform(1.2, 1.9),
            rng.uniform(1.0, 1.6),
        )

        noise = nodes.new(type="ShaderNodeTexNoise")
        noise.location = (-520, 110)
        noise.inputs["Scale"].default_value = rng.uniform(5.0, 10.0)
        noise.inputs["Detail"].default_value = rng.uniform(7.0, 11.0)
        noise.inputs["Roughness"].default_value = 0.54

        gradient = nodes.new(type="ShaderNodeTexGradient")
        gradient.location = (-520, -120)
        gradient.gradient_type = "SPHERICAL"

        mix_value = nodes.new(type="ShaderNodeMath")
        mix_value.location = (-300, 0)
        mix_value.operation = "MULTIPLY"
        mix_value.inputs[1].default_value = rng.uniform(0.65, 0.9)

        ramp = nodes.new(type="ShaderNodeValToRGB")
        ramp.location = (-60, 10)
        ramp.color_ramp.elements[0].position = 0.18
        ramp.color_ramp.elements[1].position = 0.84
        low_color, high_color = rng.choice(self.URCHIN_PALETTES)
        ramp.color_ramp.elements[0].color = low_color
        ramp.color_ramp.elements[1].color = high_color

        bump = nodes.new(type="ShaderNodeBump")
        bump.location = (30, -180)
        bump.inputs["Strength"].default_value = rng.uniform(0.03, 0.08)
        bump.inputs["Distance"].default_value = 0.05

        roughness_ramp = nodes.new(type="ShaderNodeMapRange")
        roughness_ramp.location = (-60, -250)
        roughness_ramp.inputs["To Min"].default_value = rng.uniform(0.28, 0.38)
        roughness_ramp.inputs["To Max"].default_value = rng.uniform(0.52, 0.7)

        links.new(coord.outputs["Object"], mapping.inputs["Vector"])
        links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
        links.new(mapping.outputs["Vector"], gradient.inputs["Vector"])
        links.new(noise.outputs["Fac"], mix_value.inputs[0])
        links.new(gradient.outputs["Fac"], mix_value.inputs[1])
        links.new(mix_value.outputs["Value"], ramp.inputs["Fac"])
        links.new(noise.outputs["Fac"], bump.inputs["Height"])
        links.new(gradient.outputs["Fac"], roughness_ramp.inputs["Value"])
        links.new(ramp.outputs["Color"], principled.inputs["Base Color"])
        links.new(roughness_ramp.outputs["Result"], principled.inputs["Roughness"])
        links.new(bump.outputs["Normal"], principled.inputs["Normal"])
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])

        return material

    @staticmethod
    def _make_box_geometry(width, depth, height):
        half_x = width * 0.5
        half_y = depth * 0.5
        half_z = height * 0.5
        vertices = [
            (-half_x, -half_y, -half_z),
            (half_x, -half_y, -half_z),
            (half_x, half_y, -half_z),
            (-half_x, half_y, -half_z),
            (-half_x, -half_y, half_z),
            (half_x, -half_y, half_z),
            (half_x, half_y, half_z),
            (-half_x, half_y, half_z),
        ]
        faces = [
            (0, 1, 2, 3),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
        ]
        return vertices, faces

    @staticmethod
    def _make_sphere_core_geometry(radius, rings, sides):
        vertices = [(0.0, 0.0, radius)]
        faces = []
        ring_starts = []

        for ring_index in range(1, rings):
            phi = (math.pi * ring_index) / rings
            ring_radius = math.sin(phi) * radius
            z = math.cos(phi) * radius
            ring_starts.append(len(vertices))
            for side in range(sides):
                angle = (math.tau * side) / sides
                vertices.append((math.cos(angle) * ring_radius, math.sin(angle) * ring_radius, z))

        bottom_index = len(vertices)
        vertices.append((0.0, 0.0, -radius))

        first_ring = ring_starts[0]
        for side in range(sides):
            next_side = (side + 1) % sides
            faces.append((0, first_ring + side, first_ring + next_side))

        for ring_index in range(len(ring_starts) - 1):
            current_start = ring_starts[ring_index]
            next_start = ring_starts[ring_index + 1]
            for side in range(sides):
                next_side = (side + 1) % sides
                faces.append(
                    (
                        current_start + side,
                        current_start + next_side,
                        next_start + next_side,
                        next_start + side,
                    )
                )

        last_ring = ring_starts[-1]
        for side in range(sides):
            next_side = (side + 1) % sides
            faces.append((last_ring + next_side, last_ring + side, bottom_index))

        return vertices, faces

    @staticmethod
    def _make_cone_spike_geometry(length, base_radius, sides):
        vertices = [(0.0, 0.0, 0.0)]
        faces = []
        ring_start = len(vertices)

        for side in range(sides):
            angle = (math.tau * side) / sides
            vertices.append((math.cos(angle) * base_radius, math.sin(angle) * base_radius, 0.0))

        tip_index = len(vertices)
        vertices.append((0.0, 0.0, length))

        for side in range(sides):
            next_side = ((side + 1) % sides) + ring_start
            current_side = side + ring_start
            faces.append((0, next_side, current_side))
            faces.append((current_side, next_side, tip_index))

        return vertices, faces

    def _make_prism_spike_geometry(self, length, width, depth, tip_scale):
        vertices = []
        faces = []

        rod_vertices, rod_faces = self._make_box_geometry(width, depth, length * 0.78)
        self._append_transformed_geometry(
            vertices,
            faces,
            rod_vertices,
            rod_faces,
            offset=(0.0, 0.0, length * 0.39),
        )

        tip_vertices, tip_faces = self._make_box_geometry(width * tip_scale, depth * tip_scale, length * 0.22)
        self._append_transformed_geometry(
            vertices,
            faces,
            tip_vertices,
            tip_faces,
            offset=(0.0, 0.0, length * 0.89),
        )

        return vertices, faces

    def _append_transformed_geometry(self, vertices, faces, new_vertices, new_faces, offset=(0.0, 0.0, 0.0)):
        base_index = len(vertices)
        ox, oy, oz = offset
        for vertex in new_vertices:
            vertices.append((vertex[0] + ox, vertex[1] + oy, vertex[2] + oz))
        for face in new_faces:
            faces.append(tuple(base_index + index for index in face))

    def _append_oriented_geometry(self, vertices, faces, new_vertices, new_faces, offset, direction):
        base_index = len(vertices)
        dx, dy, dz = direction
        length = math.sqrt((dx * dx) + (dy * dy) + (dz * dz))
        if length <= 1e-8:
            return

        dx /= length
        dy /= length
        dz /= length

        if abs(dz) < 0.95:
            ref = (0.0, 0.0, 1.0)
        else:
            ref = (0.0, 1.0, 0.0)

        tx = ref[1] * dz - ref[2] * dy
        ty = ref[2] * dx - ref[0] * dz
        tz = ref[0] * dy - ref[1] * dx
        tangent_length = math.sqrt((tx * tx) + (ty * ty) + (tz * tz))
        tx /= tangent_length
        ty /= tangent_length
        tz /= tangent_length

        bx = dy * tz - dz * ty
        by = dz * tx - dx * tz
        bz = dx * ty - dy * tx

        ox, oy, oz = offset
        for x, y, z in new_vertices:
            vertices.append(
                (
                    ox + (tx * x) + (bx * y) + (dx * z),
                    oy + (ty * x) + (by * y) + (dy * z),
                    oz + (tz * x) + (bz * y) + (dz * z),
                )
            )

        for face in new_faces:
            faces.append(tuple(base_index + index for index in face))

    @staticmethod
    def _random_unit_vector(rng):
        z = rng.uniform(-0.22, 1.0)
        angle = rng.uniform(0.0, math.tau)
        radial = math.sqrt(max(0.0, 1.0 - (z * z)))
        return (math.cos(angle) * radial, math.sin(angle) * radial, z)

    def _corrupted_direction(self, rng, corruption_level):
        base_x, base_y, base_z = rng.choice(self.CORRUPTED_DIRECTIONS)
        jitter = 0.24 * (1.0 - corruption_level)
        direction = (
            base_x + rng.uniform(-jitter, jitter),
            base_y + rng.uniform(-jitter, jitter),
            max(0.08, base_z + rng.uniform(-jitter, jitter)),
        )
        length = math.sqrt(sum(component * component for component in direction))
        return tuple(component / length for component in direction)

    def _glitch_vertices(self, vertices, rng, corruption_level, apply_glitch):
        if apply_glitch is None or corruption_level <= 0.0:
            return vertices

        amount = 0.06 * corruption_level
        snap_amount = max(0.0, corruption_level - 0.25) / 0.75
        glitched = []
        for vertex in vertices:
            x, y, z = apply_glitch(vertex, amount, rng)
            glitched.append(
                (
                    self._snap_lerp(x, snap_amount),
                    self._snap_lerp(y, snap_amount),
                    self._snap_lerp(z, snap_amount * 0.7),
                )
            )
        return glitched

    def _finish_mesh(self, obj, mesh, rng, name):
        mesh.update()
        mesh.polygons.foreach_set("use_smooth", [False] * len(mesh.polygons))
        mesh.materials.append(self._build_urchin_material(f"{name}_Material", rng))

        bevel = obj.modifiers.new(name="Bevel", type="BEVEL")
        bevel.width = rng.uniform(*self.bevel_width_range)
        bevel.segments = 2
        bevel.limit_method = "ANGLE"

        return obj

    def _create_urchin_mesh(self, name, rng, corruption_level=0.0, apply_glitch=None):
        mesh = bpy.data.meshes.new(f"{name}_Mesh")
        obj = bpy.data.objects.new(name, mesh)

        vertices = []
        faces = []
        urchin_types = []

        core_radius = rng.uniform(0.16, 0.34)
        if corruption_level < 0.58:
            core_vertices, core_faces = self._make_sphere_core_geometry(
                radius=core_radius,
                rings=rng.randint(4, 6),
                sides=rng.randint(10, 14),
            )
            urchin_types.append("organic_core")
        else:
            core_vertices, core_faces = self._make_box_geometry(
                width=core_radius * rng.uniform(1.5, 2.2),
                depth=core_radius * rng.uniform(1.3, 2.0),
                height=core_radius * rng.uniform(1.2, 1.8),
            )
            urchin_types.append("header_core")

        self._append_transformed_geometry(vertices, faces, core_vertices, core_faces, offset=(0.0, 0.0, core_radius * 0.55))

        spine_count = rng.randint(16, 30)
        for _ in range(spine_count):
            use_pin = rng.random() < self._lerp(0.12, 0.92, corruption_level)
            if use_pin:
                spike_vertices, spike_faces = self._make_prism_spike_geometry(
                    length=rng.uniform(0.24, 0.82),
                    width=rng.uniform(0.025, 0.06),
                    depth=rng.uniform(0.025, 0.06),
                    tip_scale=rng.uniform(1.05, 1.4),
                )
                direction = self._corrupted_direction(rng, corruption_level)
                urchin_types.append("pin")
            else:
                spike_vertices, spike_faces = self._make_cone_spike_geometry(
                    length=rng.uniform(0.22, 0.72),
                    base_radius=rng.uniform(0.02, 0.055),
                    sides=rng.randint(4, 7),
                )
                direction = self._random_unit_vector(rng)
                urchin_types.append("spine")

            origin = (
                direction[0] * core_radius * 0.35,
                direction[1] * core_radius * 0.35,
                (core_radius * 0.55) + (direction[2] * core_radius * 0.35),
            )
            self._append_oriented_geometry(vertices, faces, spike_vertices, spike_faces, origin, direction)

        if corruption_level > 0.62 and rng.random() < 0.45:
            mast_vertices, mast_faces = self._make_prism_spike_geometry(
                length=rng.uniform(0.45, 0.95),
                width=rng.uniform(0.05, 0.1),
                depth=rng.uniform(0.05, 0.1),
                tip_scale=rng.uniform(1.2, 1.55),
            )
            self._append_oriented_geometry(
                vertices,
                faces,
                mast_vertices,
                mast_faces,
                offset=(0.0, 0.0, core_radius * 0.8),
                direction=(0.0, 0.0, 1.0),
            )
            urchin_types.append("mast")

        vertices = self._glitch_vertices(vertices, rng, corruption_level, apply_glitch)
        mesh.from_pydata(vertices, [], faces)
        finished = self._finish_mesh(obj, mesh, rng, name)
        finished["urchin_mix"] = ",".join(sorted(set(urchin_types)))
        return finished

    def build_patch(
        self,
        collection,
        seed=None,
        origin=(0.0, 0.0, 0.0),
        corruption_level=0.0,
        apply_glitch=None,
        rng=None,
    ):
        rng = rng or random.Random(seed)
        half_area = self.patch_area_size * 0.5
        generated_objects = []

        for index in range(self.patch_count):
            obj = self._create_urchin_mesh(
                name=f"Urchin_{index:02d}",
                rng=rng,
                corruption_level=corruption_level,
                apply_glitch=apply_glitch,
            )

            scale = rng.uniform(*self.scale_range)
            obj.location = (
                origin[0] + rng.uniform(-half_area, half_area),
                origin[1] + rng.uniform(-half_area, half_area),
                origin[2] + rng.uniform(0.0, 0.08),
            )
            obj.rotation_euler = (
                rng.uniform(-0.16, 0.16) * (1.0 - corruption_level),
                rng.uniform(-0.16, 0.16) * (1.0 - corruption_level),
                rng.uniform(0.0, math.tau),
            )
            obj.scale = (scale, scale, scale)
            obj["coral_type"] = "urchin"
            obj["corruption_level"] = corruption_level

            collection.objects.link(obj)
            generated_objects.append(obj)

        return generated_objects
