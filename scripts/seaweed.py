import math
import random

import bpy


class SeaweedGenerator:
    SEAWEED_PALETTES = (
        ((0.08, 0.17, 0.08, 1.0), (0.29, 0.46, 0.17, 1.0)),
        ((0.1, 0.22, 0.12, 1.0), (0.42, 0.57, 0.2, 1.0)),
        ((0.07, 0.16, 0.13, 1.0), (0.26, 0.42, 0.24, 1.0)),
    )

    def __init__(
        self,
        patch_count=480,
        patch_area_size=40.0,
        height_range=(1.8, 5.4),
        width_range=(0.14, 0.6),
        segment_range=(8, 24),
        noise_scale_range=(0.18, 0.42),
        scale_range=(0.9, 1.35),
        lean_range=(-0.06, 0.06),
        snap_increment=0.1,
    ):
        self.patch_count = patch_count
        self.patch_area_size = patch_area_size
        self.height_range = height_range
        self.width_range = width_range
        self.segment_range = segment_range
        self.noise_scale_range = noise_scale_range
        self.scale_range = scale_range
        self.lean_range = lean_range
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

    def _build_seaweed_material(self, name, rng):
        material = bpy.data.materials.new(name=name)
        material.use_nodes = True
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        nodes.clear()

        output = nodes.new(type="ShaderNodeOutputMaterial")
        output.location = (620, 0)

        principled = nodes.new(type="ShaderNodeBsdfPrincipled")
        principled.location = (340, 0)
        self._set_node_input(principled, ("Roughness",), rng.uniform(0.42, 0.62))
        self._set_node_input(principled, ("Subsurface Weight", "Subsurface"), rng.uniform(0.04, 0.1))
        self._set_node_input(principled, ("Subsurface Radius",), (0.4, 0.85, 0.2))
        self._set_node_input(principled, ("Specular IOR Level", "Specular"), rng.uniform(0.22, 0.34))

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
        low_color, high_color = rng.choice(self.SEAWEED_PALETTES)
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

    @staticmethod
    def _centerline_point(t, height, noise_scale, curvature):
        z = t * height
        phase = curvature["phase"]
        twist = curvature["twist_turns"] * math.tau * t + phase
        sweep = curvature["sweep_frequency"] * math.pi * t + phase * 0.35
        ribbon_belly = math.sin(math.pi * t) ** 1.15
        tip_zone = max(0.0, t - 0.68) / 0.32

        radius = noise_scale * curvature["helix_radius"] * (0.2 + 0.55 * t)
        x = math.sin(twist) * radius
        x += math.sin(sweep) * curvature["side_arc"] * (t**1.15)
        x += math.cos(sweep * 0.55 + phase) * curvature["belly"] * ribbon_belly * 0.4
        x += curvature["tip_curl_x"] * (tip_zone**2.1)

        y = math.cos(twist * 0.72) * radius * 0.8
        y += math.cos(sweep * 0.9) * curvature["forward_arc"] * (t**1.1)
        y += math.sin(sweep * 0.6 - phase) * curvature["belly"] * ribbon_belly
        y += curvature["tip_curl_y"] * (tip_zone**2.0)
        return x, y, z, twist

    def _append_connector_cube(self, vertices, faces, center, size):
        half = size * 0.5
        cx, cy, cz = center
        connector = [
            (cx - half, cy - half, cz - half),
            (cx + half, cy - half, cz - half),
            (cx + half, cy + half, cz - half),
            (cx - half, cy + half, cz - half),
            (cx - half, cy - half, cz + half),
            (cx + half, cy - half, cz + half),
            (cx + half, cy + half, cz + half),
            (cx - half, cy + half, cz + half),
        ]
        base = len(vertices)
        vertices.extend(connector)
        faces.extend(
            (
                (base + 0, base + 1, base + 2, base + 3),
                (base + 4, base + 5, base + 6, base + 7),
                (base + 0, base + 1, base + 5, base + 4),
                (base + 1, base + 2, base + 6, base + 5),
                (base + 2, base + 3, base + 7, base + 6),
                (base + 3, base + 0, base + 4, base + 7),
            )
        )

    @staticmethod
    def _add_scene_frame_driver(target, data_path, expression):
        fcurve = target.driver_add(data_path)
        driver = fcurve.driver
        driver.type = "SCRIPTED"

        frame_var = driver.variables.new()
        frame_var.name = "frame"
        frame_target = frame_var.targets[0]
        frame_target.id_type = "SCENE"
        frame_target.id = bpy.context.scene
        frame_target.data_path = "frame_current"

        driver.expression = expression

    def _configure_sway_shape_keys(self, obj, sway_weights, height, dramatic, corruption_level, rng):
        obj.shape_key_add(name="Basis", from_mix=False)
        primary_key = obj.shape_key_add(name="Sway_Primary", from_mix=False)
        secondary_key = obj.shape_key_add(name="Sway_Secondary", from_mix=False)

        primary_key.slider_min = -1.0
        primary_key.slider_max = 1.0
        secondary_key.slider_min = -1.0
        secondary_key.slider_max = 1.0

        primary_extent = height * self._lerp(0.085, 0.04, corruption_level) * (0.9 + dramatic * 0.3)
        secondary_extent = primary_extent * self._lerp(0.42, 0.24, corruption_level) * rng.uniform(0.9, 1.15)
        tip_drag = self._lerp(0.16, 0.08, corruption_level)
        cross_pull = self._lerp(0.05, 0.025, corruption_level)

        for vertex_index, sway_weight in enumerate(sway_weights):
            bend = math.sin(sway_weight * math.pi * 0.5) ** 1.35
            mid_belly = math.sin(sway_weight * math.pi) * 0.2
            tip_bias = max(0.0, sway_weight - 0.18) ** 1.45

            primary_data = primary_key.data[vertex_index].co
            primary_data.x += primary_extent * bend
            primary_data.y += primary_extent * tip_drag * tip_bias

            secondary_data = secondary_key.data[vertex_index].co
            secondary_data.y += secondary_extent * (bend + mid_belly)
            secondary_data.x += secondary_extent * cross_pull * tip_bias

        primary_amplitude = self._lerp(rng.uniform(0.72, 0.96), rng.uniform(0.35, 0.58), corruption_level)
        primary_speed = self._lerp(rng.uniform(0.03, 0.05), rng.uniform(0.04, 0.07), corruption_level)
        primary_phase = rng.uniform(0.0, math.tau)
        primary_detail_speed = primary_speed * rng.uniform(0.42, 0.6)
        primary_detail_phase = primary_phase + rng.uniform(0.6, 1.4)

        secondary_amplitude = primary_amplitude * rng.uniform(0.35, 0.5)
        secondary_speed = primary_speed * rng.uniform(1.35, 1.8)
        secondary_phase = primary_phase + rng.uniform(0.9, 1.8)
        secondary_detail_speed = secondary_speed * rng.uniform(0.45, 0.7)
        secondary_detail_phase = secondary_phase + rng.uniform(0.5, 1.2)

        self._add_scene_frame_driver(
            primary_key,
            "value",
            (
                f"{primary_amplitude:.4f} * "
                f"(sin(frame * {primary_speed:.5f} + {primary_phase:.5f}) + "
                f"0.35 * sin(frame * {primary_detail_speed:.5f} + {primary_detail_phase:.5f}))"
            ),
        )
        self._add_scene_frame_driver(
            secondary_key,
            "value",
            (
                f"{secondary_amplitude:.4f} * "
                f"(sin(frame * {secondary_speed:.5f} + {secondary_phase:.5f}) + "
                f"0.28 * sin(frame * {secondary_detail_speed:.5f} + {secondary_detail_phase:.5f}))"
            ),
        )

    def create_seaweed_mesh(
        self,
        name,
        height,
        segments,
        noise_scale,
        width,
        curvature,
        dramatic=0.0,
        corruption_level=0.0,
        rng=None,
        apply_glitch=None,
    ):
        mesh = bpy.data.meshes.new(f"{name}_Mesh")
        obj = bpy.data.objects.new(name, mesh)
        rng = rng or random.Random()

        segments = max(2, int(segments))
        vertices = []
        faces = []
        weights = []

        for index in range(segments):
            t = index / (segments - 1)
            center_x, center_y, center_z, twist = self._centerline_point(t, height, noise_scale, curvature)

            organic_taper = max(0.12, (1.0 - t) ** curvature["taper_power"])
            taper = self._lerp(organic_taper, 1.0, corruption_level)
            half_width = width * 0.5 * taper

            normal_angle = twist + (math.pi * 0.5)
            offset_x = math.cos(normal_angle) * half_width
            offset_y = math.sin(normal_angle) * half_width

            pair = [
                [center_x - offset_x, center_y - offset_y, center_z],
                [center_x + offset_x, center_y + offset_y, center_z],
            ]

            for point in pair:
                if apply_glitch is not None and corruption_level > 0.0:
                    point[0], point[1], point[2] = apply_glitch(
                        (point[0], point[1], point[2]), corruption_level * 0.08, rng
                    )

                point[0] = self._snap_lerp(point[0], corruption_level)
                point[1] = self._snap_lerp(point[1], corruption_level)
                point[2] = self._snap_lerp(point[2], corruption_level)

                vertices.append((point[0], point[1], point[2]))
                weights.append(t)

        for index in range(segments - 1):
            base = index * 2
            faces.append((base, base + 1, base + 3, base + 2))

        connector_size = self._lerp(0.0, 0.18, corruption_level)
        if connector_size > 0.005:
            tip_left = vertices[-2]
            tip_right = vertices[-1]
            tip_center = (
                (tip_left[0] + tip_right[0]) * 0.5,
                (tip_left[1] + tip_right[1]) * 0.5,
                (tip_left[2] + tip_right[2]) * 0.5,
            )
            self._append_connector_cube(vertices, faces, tip_center, connector_size)

        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        mesh.polygons.foreach_set("use_smooth", [False] * len(mesh.polygons))

        sway_weights = list(weights)
        if len(sway_weights) < len(vertices):
            sway_weights.extend([1.0] * (len(vertices) - len(sway_weights)))

        sway_group = obj.vertex_groups.new(name="Sway_Weight")
        for vertex_index, weight in enumerate(sway_weights):
            sway_group.add([vertex_index], weight, "REPLACE")
        self._configure_sway_shape_keys(obj, sway_weights, height, dramatic, corruption_level, rng)

        return obj

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
            curve_seed = rng.random()
            dramatic = rng.random()
            height = rng.uniform(*self.height_range)
            segments = rng.randint(*self.segment_range)
            noise_scale = rng.uniform(*self.noise_scale_range)
            width = rng.uniform(*self.width_range)
            scale = rng.uniform(*self.scale_range)
            curl_sign = -1.0 if rng.random() < 0.5 else 1.0

            base_twist = rng.uniform(0.2, 1.1)
            base_side_arc = rng.uniform(0.12, 0.32) * (0.9 + dramatic * 0.4)
            base_forward_arc = rng.uniform(0.06, 0.2) * (0.85 + dramatic * 0.35)

            curvature = {
                "phase": curve_seed * math.tau,
                "twist_turns": self._lerp(base_twist, 0.12, corruption_level),
                "sweep_frequency": self._lerp(rng.uniform(0.45, 1.1), 0.15, corruption_level),
                "helix_radius": self._lerp(rng.uniform(0.03, 0.08), 0.01, corruption_level),
                "side_arc": self._lerp(base_side_arc, 0.02, corruption_level),
                "forward_arc": self._lerp(base_forward_arc, 0.02, corruption_level),
                "belly": self._lerp(rng.uniform(0.05, 0.16), 0.01, corruption_level),
                "tip_curl_x": self._lerp(
                    curl_sign * rng.uniform(0.02, 0.22) * (0.5 + dramatic * 0.7),
                    0.0,
                    corruption_level,
                ),
                "tip_curl_y": self._lerp(
                    -curl_sign * rng.uniform(0.01, 0.16) * (0.45 + dramatic * 0.6),
                    0.0,
                    corruption_level,
                ),
                "taper_power": self._lerp(rng.uniform(1.15, 1.85), 0.0, corruption_level),
            }

            obj = self.create_seaweed_mesh(
                name=f"Seaweed_{index:02d}",
                height=height,
                segments=segments,
                noise_scale=noise_scale,
                width=width,
                curvature=curvature,
                dramatic=dramatic,
                corruption_level=corruption_level,
                rng=rng,
                apply_glitch=apply_glitch,
            )
            obj.data.materials.append(self._build_seaweed_material(f"{obj.name}_Material", rng))
            obj["curve_seed"] = curve_seed
            obj["dramatic"] = dramatic
            obj["corruption_level"] = corruption_level

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

            collection.objects.link(obj)
            generated_objects.append(obj)

        return generated_objects
