import importlib
import importlib.util
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
THREE_SECTOR_NAMES = ("Left", "Forward", "Right")


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
                    if material is not None and material not in owned_materials:
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


class WorldGenerator:
    def __init__(
        self,
        world_collection_name=WORLD_COLLECTION_NAME,
        sector_spacing=20.0,
        seaweed_generator=None,
        coral_generator=None,
    ):
        self.world_collection_name = world_collection_name
        self.sector_spacing = sector_spacing
        self.seaweed_generator = seaweed_generator or SeaweedGenerator()
        self.coral_generator = coral_generator or CoralGenerator()

    @staticmethod
    def clamp01(value):
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def apply_glitch(vector, amount, rng):
        amount = WorldGenerator.clamp01(amount)
        jitter_strength = 0.22 * amount
        return (
            vector[0] + rng.uniform(-jitter_strength, jitter_strength),
            vector[1] + rng.uniform(-jitter_strength, jitter_strength),
            vector[2] + rng.uniform(-jitter_strength, jitter_strength),
        )

    def purge_world(self):
        world_collection = ensure_collection(self.world_collection_name)
        clear_collection_objects(world_collection)
        return world_collection

    def _normalize_corruption_levels(self, corruption_levels):
        if corruption_levels is None:
            corruption_levels = [0.0, 0.5, 1.0]

        levels = [self.clamp01(value) for value in corruption_levels]
        if not levels:
            raise ValueError("corruption_levels must contain at least one value.")
        return levels

    @staticmethod
    def _sector_name(index, total):
        if total == 3:
            return THREE_SECTOR_NAMES[index]
        return f"Sector_{index:02d}"

    def _sector_center(self, index, total):
        centered_index = index - ((total - 1) * 0.5)
        return (centered_index * self.sector_spacing, 0.0, 0.0)

    def generate_world(self, seed, corruption_levels=None):
        levels = self._normalize_corruption_levels(corruption_levels)
        world_collection = self.purge_world()
        master_rng = random.Random(seed)
        total = len(levels)

        for index, corruption_level in enumerate(levels):
            sector_name = self._sector_name(index, total)
            sector_collection = ensure_collection(f"Sector_{sector_name}", parent=world_collection)
            sector_center = self._sector_center(index, total)
            sector_collection["corruption_level"] = corruption_level

            seaweed_rng = random.Random(master_rng.randint(0, 10**9))
            coral_rng = random.Random(master_rng.randint(0, 10**9))

            self.seaweed_generator.build_patch(
                collection=sector_collection,
                origin=sector_center,
                corruption_level=corruption_level,
                apply_glitch=self.apply_glitch,
                rng=seaweed_rng,
            )
            self.coral_generator.build_patch(
                collection=sector_collection,
                origin=sector_center,
                corruption_level=corruption_level,
                apply_glitch=self.apply_glitch,
                rng=coral_rng,
            )

        return world_collection


def generate_world(seed, corruption_levels=None):
    return WorldGenerator().generate_world(seed, corruption_levels)
