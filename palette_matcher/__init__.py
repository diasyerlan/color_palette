"""Extract dominant image colours and match them to Color Hunt palettes."""

from .core import ExtractedPalette, PaletteMatch, extract_dominant_colors, find_similar_palettes

__all__ = [
    "ExtractedPalette",
    "PaletteMatch",
    "extract_dominant_colors",
    "find_similar_palettes",
]
