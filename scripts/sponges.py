import math
import random

import bpy


class SpongeGenerator:
    SPONGE_PALETTES = (
        ((0.54, 0.44, 0.24, 1.0), (0.79, 0.67, 0.38, 1.0)),
        ((0.42, 0.35, 0.18, 1.0), (0.71, 0.6, 0.34, 1.0)),
        ((0.47, 0.3, 0.16, 1.0), (0.8, 0.56, 0.3, 1.0)),
    )

    def __init__(
        self,
        patch_count=52,
        patch_area_size=80.0,
        scale_range=(0.75, 1.35),
        lean_range=(-0.08, 0.08),
        bevel_width_range=(0.006, 0.016),
        snap_increment=0.08,
    ):
        self.patch_count = patch_count
        self.patch_area_size = patch_area_size
        self.scale_range = scale_range
        self.lean_range = lean_range
        self.bevel_width_range = bevel_width_range
        self.snap_increment = snap_increment

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

    def _build_sponge_material(self, name, rng):
        material = bpy.data.materials.new(name=name)
        material.use_nodes = True
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        nodes.clear()

        output = nodes.new(type="ShaderNodeOutputMaterial")
        output.location = (520, 0)

        principled = nodes.new(type="ShaderNodeBsdfPrincipled")
        principled.location = (260, 0)
        self._set_node_input(principled, ("Roughness",), rng.uniform(0.58, 0.82))
        self._set_node_input(principled, ("Subsurface Weight", "Subsurface"), rng.uniform(0.02, 0.08))
        self._set_node_input(principled, ("Subsurface Radius",), (1.0, 0.6, 0.35))
        self._set_node_input(principled, ("Specular IOR Level", "Specular"), rng.uniform(0.18, 0.3))

        coord = nodes.new(type="ShaderNodeTexCoord")
        coord.location = (-920, 0)

        mapping = nodes.new(type="ShaderNodeMapping")
        mapping.location = (-720, 0)
        mapping.inputs["Scale"].default_value = (
            rng.uniform(1.6, 2.6),
            rng.uniform(1.6, 2.6),
            rng.uniform(1.0, 1.5),
        )

        noise = nodes.new(type="ShaderNodeTexNoise")
        noise.location = (-520, 120)
        noise.inputs["Scale"].default_value = rng.uniform(4.5, 8.5)
        noise.inputs["Detail"].default_value = rng.uniform(7.0, 11.0)
        noise.inputs["Roughness"].default_value = 0.6

        voronoi = nodes.new(type="ShaderNodeTexVoronoi")
        voronoi.location = (-520, -120)
        voronoi.feature = "SMOOTH_F1"
        voronoi.inputs["Scale"].default_value = rng.uniform(5.0, 11.0)

        mix_value = nodes.new(type="ShaderNodeMath")
        mix_value.location = (-290, 0)
        mix_value.operation = "MULTIPLY"
        mix_value.inputs[1].default_value = rng.uniform(0.55, 0.9)

        ramp = nodes.new(type="ShaderNodeValToRGB")
        ramp.location = (-50, 10)
        ramp.color_ramp.elements[0].position = 0.22
        ramp.color_ramp.elements[1].position = 0.88
        low_color, high_color = rng.choice(self.SPONGE_PALETTES)
        ramp.color_ramp.elements[0].color = low_color
        ramp.color_ramp.elements[1].color = high_color

        bump = nodes.new(type="ShaderNodeBump")
        bump.location = (50, -180)
        bump.inputs["Strength"].default_value = rng.uniform(0.04, 0.1)
        bump.inputs["Distance"].default_value = 0.07

        roughness_ramp = nodes.new(type="ShaderNodeMapRange")
        roughness_ramp.location = (-70, -250)
        roughness_ramp.inputs["To Min"].default_value = rng.uniform(0.48, 0.58)
        roughness_ramp.inputs["To Max"].default_value = rng.uniform(0.74, 0.9)

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

    @staticmethod
    def _rotate_point(point, rotation):
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

    def _append_transformed_geometry(
        self,
        vertices,
        faces,
        new_vertices,
        new_faces,
        offset=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0),
    ):
        base_index = len(vertices)
        ox, oy, oz = offset

        for vertex in new_vertices:
            tx, ty, tz = self._rotate_point(vertex, rotation)
            vertices.append((tx + ox, ty + oy, tz + oz))

        for face in new_faces:
            faces.append(tuple(base_index + index for index in face))

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
    def _make_mound_geometry(radius_x, radius_y, height, sides):
        vertices = [(0.0, 0.0, 0.0)]
        faces = []
        ring_starts = []
        ring_profiles = (
            (1.0, height * 0.08, 0.18),
            (0.86, height * 0.32, 0.14),
            (0.62, height * 0.72, 0.1),
        )

        for scale, z_height, wobble in ring_profiles:
            ring_starts.append(len(vertices))
            for side in range(sides):
                angle = (math.tau * side) / sides
                radial_noise = 1.0 + (math.sin(angle * 3.0) * wobble) + (math.cos(angle * 5.0) * wobble * 0.5)
                vertices.append(
                    (
                        math.cos(angle) * radius_x * scale * radial_noise,
                        math.sin(angle) * radius_y * scale * radial_noise,
                        z_height,
                    )
                )

        top_index = len(vertices)
        vertices.append((0.0, 0.0, height))

        for side in range(sides):
            next_side = (side + 1) % sides
            faces.append((0, ring_starts[0] + next_side, ring_starts[0] + side))

            for ring_index in range(len(ring_starts) - 1):
                current_start = ring_starts[ring_index]
                next_start = ring_starts[ring_index + 1]
                faces.append(
                    (
                        current_start + side,
                        current_start + next_side,
                        next_start + next_side,
                        next_start + side,
                    )
                )

            faces.append((ring_starts[-1] + side, ring_starts[-1] + next_side, top_index))

        return vertices, faces

    @staticmethod
    def _make_tube_shell_geometry(radius_x, radius_y, inner_scale, height, sides, flare):
        vertices = []
        faces = []
        ring_starts = []

        profiles = (
            (radius_x, radius_y, 0.0),
            (radius_x * (1.0 + flare), radius_y * (1.0 + flare), height),
        )

        for outer_x, outer_y, z in profiles:
            outer_start = len(vertices)
            for side in range(sides):
                angle = (math.tau * side) / sides
                vertices.append((math.cos(angle) * outer_x, math.sin(angle) * outer_y, z))

            inner_start = len(vertices)
            inner_x = outer_x * inner_scale
            inner_y = outer_y * inner_scale
            for side in range(sides):
                angle = (math.tau * side) / sides
                vertices.append((math.cos(angle) * inner_x, math.sin(angle) * inner_y, z))

            ring_starts.append((outer_start, inner_start))

        bottom_outer, bottom_inner = ring_starts[0]
        top_outer, top_inner = ring_starts[1]

        for side in range(sides):
            next_side = (side + 1) % sides
            faces.append((bottom_outer + side, bottom_outer + next_side, top_outer + next_side, top_outer + side))
            faces.append((bottom_inner + next_side, bottom_inner + side, top_inner + side, top_inner + next_side))
            faces.append((top_outer + side, top_outer + next_side, top_inner + next_side, top_inner + side))
            faces.append((bottom_inner + side, bottom_inner + next_side, bottom_outer + next_side, bottom_outer + side))

        return vertices, faces

    def _make_frame_tower_geometry(self, width, depth, wall, height, rng):
        vertices = []
        faces = []
        wall = max(wall, min(width, depth) * 0.12)

        wall_specs = (
            (wall, depth, height, (-width * 0.5 + wall * 0.5, 0.0, height * 0.5)),
            (wall, depth, height, (width * 0.5 - wall * 0.5, 0.0, height * 0.5)),
            (width - wall * 2.0, wall, height, (0.0, depth * 0.5 - wall * 0.5, height * 0.5)),
            (width - wall * 2.0, wall, height, (0.0, -depth * 0.5 + wall * 0.5, height * 0.5)),
        )

        for wall_width, wall_depth, wall_height, offset in wall_specs:
            wall_vertices, wall_faces = self._make_box_geometry(wall_width, wall_depth, wall_height)
            self._append_transformed_geometry(vertices, faces, wall_vertices, wall_faces, offset=offset)

        if rng.random() < 0.55:
            brace_vertices, brace_faces = self._make_box_geometry(width * 0.78, wall * rng.uniform(0.55, 0.95), wall)
            self._append_transformed_geometry(
                vertices,
                faces,
                brace_vertices,
                brace_faces,
                offset=(0.0, 0.0, height * rng.uniform(0.32, 0.72)),
            )

        return vertices, faces

    def _glitch_vertices(self, vertices, rng, corruption_level, apply_glitch):
        if apply_glitch is None or corruption_level <= 0.0:
            return vertices

        glitched = []
        amount = 0.07 * corruption_level
        snap_amount = max(0.0, corruption_level - 0.35) / 0.65
        for vertex in vertices:
            x, y, z = apply_glitch(vertex, amount, rng)
            glitched.append(
                (
                    self._snap_lerp(x, snap_amount),
                    self._snap_lerp(y, snap_amount),
                    self._snap_lerp(z, snap_amount * 0.8),
                )
            )
        return glitched

    def _finish_mesh(self, obj, mesh, rng, name, use_subsurf=True):
        mesh.update()
        mesh.polygons.foreach_set("use_smooth", [False] * len(mesh.polygons))
        mesh.materials.append(self._build_sponge_material(f"{name}_Material", rng))

        bevel = obj.modifiers.new(name="Bevel", type="BEVEL")
        bevel.width = rng.uniform(*self.bevel_width_range)
        bevel.segments = 2
        bevel.limit_method = "ANGLE"

        if use_subsurf:
            subsurf = obj.modifiers.new(name="Subdivision", type="SUBSURF")
            subsurf.levels = 1
            subsurf.render_levels = 2

        return obj

    def _create_cluster_mesh(self, name, rng, corruption_level=0.0, apply_glitch=None):
        mesh = bpy.data.meshes.new(f"{name}_Mesh")
        obj = bpy.data.objects.new(name, mesh)

        vertices = []
        faces = []
        cluster_types = []

        if corruption_level < 0.5:
            base_vertices, base_faces = self._make_mound_geometry(
                radius_x=rng.uniform(0.4, 0.92),
                radius_y=rng.uniform(0.38, 0.84),
                height=rng.uniform(0.12, 0.3),
                sides=rng.randint(10, 14),
            )
        else:
            base_vertices, base_faces = self._make_box_geometry(
                width=rng.uniform(0.6, 1.1),
                depth=rng.uniform(0.46, 0.96),
                height=rng.uniform(0.12, 0.24),
            )
            cluster_types.append("plinth")

        self._append_transformed_geometry(vertices, faces, base_vertices, base_faces)

        chimney_count = rng.randint(4, 9)
        for _ in range(chimney_count):
            angle = rng.uniform(0.0, math.tau)
            distance = rng.uniform(0.05, 0.42)
            offset = (
                math.cos(angle) * distance,
                math.sin(angle) * distance,
                rng.uniform(0.02, 0.08),
            )
            leaning = (
                rng.uniform(-0.1, 0.1) * (1.0 - corruption_level),
                rng.uniform(-0.1, 0.1) * (1.0 - corruption_level),
                rng.uniform(0.0, math.tau),
            )

            use_vent = rng.random() < self._lerp(0.15, 0.9, corruption_level)
            if use_vent:
                tower_vertices, tower_faces = self._make_frame_tower_geometry(
                    width=rng.uniform(0.18, 0.44),
                    depth=rng.uniform(0.16, 0.42),
                    wall=rng.uniform(0.03, 0.08),
                    height=rng.uniform(0.5, 1.5),
                    rng=rng,
                )
                cluster_types.append("vent")
                rotation = (
                    rng.uniform(-0.05, 0.05) * corruption_level,
                    rng.uniform(-0.05, 0.05) * corruption_level,
                    rng.uniform(0.0, math.tau),
                )
            else:
                tower_vertices, tower_faces = self._make_tube_shell_geometry(
                    radius_x=rng.uniform(0.11, 0.26),
                    radius_y=rng.uniform(0.1, 0.22),
                    inner_scale=rng.uniform(0.45, 0.7),
                    height=rng.uniform(0.55, 1.75),
                    sides=rng.randint(9, 14),
                    flare=rng.uniform(0.05, 0.18),
                )
                cluster_types.append("chimney")
                rotation = leaning

            self._append_transformed_geometry(
                vertices,
                faces,
                tower_vertices,
                tower_faces,
                offset=offset,
                rotation=rotation,
            )

            if corruption_level > 0.55 and rng.random() < 0.35:
                cap_vertices, cap_faces = self._make_box_geometry(
                    width=rng.uniform(0.12, 0.26),
                    depth=rng.uniform(0.04, 0.1),
                    height=rng.uniform(0.03, 0.06),
                )
                self._append_transformed_geometry(
                    vertices,
                    faces,
                    cap_vertices,
                    cap_faces,
                    offset=(
                        offset[0],
                        offset[1],
                        offset[2] + rng.uniform(0.45, 1.4),
                    ),
                    rotation=(rng.uniform(-0.22, 0.22), rng.uniform(-0.22, 0.22), rng.uniform(0.0, math.tau)),
                )
                cluster_types.append("cap")

        vertices = self._glitch_vertices(vertices, rng, corruption_level, apply_glitch)
        mesh.from_pydata(vertices, [], faces)
        finished = self._finish_mesh(obj, mesh, rng, name, use_subsurf=corruption_level < 0.68)
        finished["sponge_mix"] = ",".join(sorted(set(cluster_types)))
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
        organic_factor = 1.0 - corruption_level

        for index in range(self.patch_count):
            obj = self._create_cluster_mesh(
                name=f"Sponge_{index:02d}",
                rng=rng,
                corruption_level=corruption_level,
                apply_glitch=apply_glitch,
            )

            scale = rng.uniform(*self.scale_range)
            obj.location = (
                origin[0] + rng.uniform(-half_area, half_area),
                origin[1] + rng.uniform(-half_area, half_area),
                origin[2],
            )
            obj.rotation_euler = (
                rng.uniform(*self.lean_range) * organic_factor,
                rng.uniform(*self.lean_range) * organic_factor,
                rng.uniform(0.0, math.tau),
            )
            obj.scale = (scale, scale, scale)
            obj["coral_type"] = "sponge"
            obj["corruption_level"] = corruption_level

            collection.objects.link(obj)
            generated_objects.append(obj)

        return generated_objects
