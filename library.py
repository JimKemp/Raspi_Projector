"""
Scans a library root into a data model. Every component (video, cover, yaml,
description) is optional and parsed defensively -- a missing or corrupt piece
degrades that one field to a sensible default and never aborts the scan.

Data model:
    Library
      └─ Category (one per media-type folder: Movies, TV, ...)
           └─ MediaItem (one per title folder)

A MediaItem may hold multiple video files (treated as episodes/parts); the
first is the default. See the README note about TV layout.
"""

import os

import config

# PyYAML is optional. If it's missing, every .yaml is simply treated as absent
# rather than crashing -- consistent with the "fail gracefully" rule.
try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


def _safe_listdir(path):
    try:
        return sorted(os.listdir(path))
    except (PermissionError, OSError):
        return []


def _find_videos(folder):
    vids = []
    for name in _safe_listdir(folder):
        full = os.path.join(folder, name)
        if os.path.isfile(full) and name.lower().endswith(config.VIDEO_EXTENSIONS):
            vids.append(full)
    return vids


def _find_cover(folder):
    names = _safe_listdir(folder)
    lower = {n.lower(): n for n in names}
    # Preferred basenames first (cover.*, poster.*, ...).
    for base in config.COVER_BASENAMES:
        for ext in config.IMAGE_EXTENSIONS:
            key = (base + ext).lower()
            if key in lower:
                return os.path.join(folder, lower[key])
    # Otherwise the first image file of any name.
    for name in names:
        if name.lower().endswith(config.IMAGE_EXTENSIONS):
            return os.path.join(folder, name)
    return None


def _find_yaml(folder):
    names = _safe_listdir(folder)
    lower = {n.lower(): n for n in names}
    for base in config.YAML_BASENAMES:
        for ext in (".yaml", ".yml"):
            key = (base + ext).lower()
            if key in lower:
                return os.path.join(folder, lower[key])
    for name in names:
        if name.lower().endswith((".yaml", ".yml")):
            return os.path.join(folder, name)
    return None


def _load_yaml(path):
    """Return a dict of metadata, or {} on any failure (missing lib, parse error, wrong type)."""
    if not path or not _HAS_YAML:
        return {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        # Corrupt YAML, encoding issues, etc. -- treat as no metadata.
        return {}


def _load_description(folder, meta):
    """description.txt takes precedence; fall back to a 'description' key in YAML."""
    path = os.path.join(folder, config.DESCRIPTION_FILENAME)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read().strip()
        except Exception:
            pass
    desc = meta.get("description")
    return str(desc).strip() if desc else ""


class MediaItem:
    def __init__(self, folder, category_name):
        self.folder = folder
        self.category = category_name
        self.folder_name = os.path.basename(folder)

        self.videos = _find_videos(folder)          # list[str], possibly empty
        self.cover_path = _find_cover(folder)        # str | None
        self.meta = _load_yaml(_find_yaml(folder))   # dict (possibly empty)
        self.description = _load_description(folder, self.meta)

    # --- Convenience accessors, all tolerant of missing metadata ---

    @property
    def title(self):
        t = self.meta.get("title")
        return str(t) if t else self.folder_name

    @property
    def has_video(self):
        return len(self.videos) > 0

    @property
    def primary_video(self):
        return self.videos[0] if self.videos else None

    @property
    def runtime(self):
        r = self.meta.get("runtime")
        if r is None:
            return None
        # Accept "169", 169, or "2h49m" -- just display whatever's there.
        if isinstance(r, (int, float)):
            return f"{int(r)} min"
        return str(r)

    @property
    def genre(self):
        g = self.meta.get("genre")
        if not g:
            return None
        if isinstance(g, (list, tuple)):
            return ", ".join(str(x) for x in g)
        return str(g)

    @property
    def series(self):
        s = self.meta.get("series")
        return str(s) if s else None

    @property
    def year(self):
        y = self.meta.get("year")
        return str(y) if y else None

    def meta_line(self):
        """A single compact line of available metadata, skipping blanks."""
        parts = [p for p in (self.year, self.runtime, self.genre) if p]
        return "  •  ".join(parts)


class Category:
    def __init__(self, name, path):
        self.name = name
        self.path = path
        self.items = []

    def __len__(self):
        return len(self.items)


def scan_library(root):
    """
    Walk root -> categories -> titles, building the model. Returns a list of
    Category objects (only non-empty categories are included). Never raises on
    a single bad folder; that folder is skipped.
    """
    categories = []
    for type_name in _safe_listdir(root):
        type_path = os.path.join(root, type_name)
        if not os.path.isdir(type_path):
            continue

        category = Category(type_name, type_path)
        for title_name in _safe_listdir(type_path):
            title_path = os.path.join(type_path, title_name)
            if not os.path.isdir(title_path):
                continue
            try:
                category.items.append(MediaItem(title_path, type_name))
            except Exception:
                # One unreadable title folder shouldn't sink the whole category.
                continue

        if category.items:
            categories.append(category)

    return categories
