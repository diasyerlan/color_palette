"""Dominant-colour extraction and perceptual palette comparison."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from itertools import permutations
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from sklearn.cluster import KMeans
from skimage.color import deltaE_ciede2000, lab2rgb, rgb2lab


@dataclass(frozen=True)
class ExtractedPalette:
    colors: tuple[str, ...]
    weights: tuple[float, ...]


@dataclass(frozen=True)
class PaletteMatch:
    rank: int
    code: str
    colors: tuple[str, ...]
    likes: int
    distance: float
    source_url: str


def _rgb_to_hex(rgb: np.ndarray) -> str:
    values = np.clip(np.rint(rgb), 0, 255).astype(int)
    return "#" + "".join(f"{value:02X}" for value in values)


def _hex_to_rgb(value: str) -> np.ndarray:
    value = value.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Invalid hex colour: {value!r}")
    return np.array([int(value[i:i + 2], 16) for i in (0, 2, 4)], dtype=float)


def extract_dominant_colors(
    image_path: str | Path,
    n_colors: int = 4,
    max_pixels: int = 50_000,
    random_state: int = 42,
) -> ExtractedPalette:
    """Extract dominant colours by deterministic k-means clustering in CIE LAB."""
    if n_colors < 1 or max_pixels < n_colors:
        raise ValueError("n_colors must be positive and no larger than max_pixels")

    with Image.open(image_path) as opened:
        image = ImageOps.exif_transpose(opened)
        if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, "white")
            image = Image.alpha_composite(background, rgba).convert("RGB")
        else:
            image = image.convert("RGB")
        pixels = np.asarray(image, dtype=np.uint8).reshape(-1, 3)

    rng = np.random.default_rng(random_state)
    if len(pixels) > max_pixels:
        pixels = pixels[rng.choice(len(pixels), max_pixels, replace=False)]
    unique_count = len(np.unique(pixels, axis=0))
    clusters = min(n_colors, unique_count)
    if clusters == 0:
        raise ValueError("The image contains no pixels")

    lab_pixels = rgb2lab(pixels.reshape(-1, 1, 3) / 255.0).reshape(-1, 3)
    model = KMeans(n_clusters=clusters, n_init=10, random_state=random_state)
    labels = model.fit_predict(lab_pixels)
    counts = np.bincount(labels, minlength=clusters)
    order = np.argsort(-counts, kind="stable")
    rgb_centers = lab2rgb(model.cluster_centers_[order].reshape(1, -1, 3)).reshape(-1, 3) * 255
    weights = counts[order] / counts.sum()
    return ExtractedPalette(
        colors=tuple(_rgb_to_hex(center) for center in rgb_centers),
        weights=tuple(float(weight) for weight in weights),
    )


def _distance_to_palette(extracted: ExtractedPalette, candidate: tuple[str, ...]) -> float:
    """Minimum weighted CIEDE2000 distance over every one-to-one colour assignment."""
    source_rgb = np.array([_hex_to_rgb(c) for c in extracted.colors]) / 255.0
    target_rgb = np.array([_hex_to_rgb(c) for c in candidate]) / 255.0
    source_lab = rgb2lab(source_rgb.reshape(1, -1, 3)).reshape(-1, 3)
    target_lab = rgb2lab(target_rgb.reshape(1, -1, 3)).reshape(-1, 3)
    matrix = deltaE_ciede2000(source_lab[:, None, :], target_lab[None, :, :])
    weights = np.asarray(extracted.weights)
    return min(
        float(np.sum(weights * matrix[np.arange(len(source_lab)), assignment]))
        for assignment in permutations(range(len(candidate)), len(source_lab))
    )


def find_similar_palettes(
    extracted: ExtractedPalette,
    csv_path: str | Path,
    top_n: int = 5,
) -> list[PaletteMatch]:
    """Rank Color Hunt CSV palettes from most to least perceptually similar."""
    if top_n < 1:
        raise ValueError("top_n must be positive")
    matches: list[PaletteMatch] = []
    with Path(csv_path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            colors = tuple(row[f"color{i}"] for i in range(1, 5))
            matches.append(
                PaletteMatch(
                    rank=int(row["rank"]),
                    code=row["code"],
                    colors=colors,
                    likes=int(row["likes"]),
                    distance=_distance_to_palette(extracted, colors),
                    source_url=row["source_url"],
                )
            )
    matches.sort(key=lambda match: (match.distance, -match.likes, match.rank))
    return matches[:top_n]
