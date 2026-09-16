from __future__ import annotations

import argparse
import json
from pathlib import Path

from .colorhunt import collect
from .core import extract_dominant_colors, find_similar_palettes

DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data" / "colorhunt_popular_100.csv"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Match image colours to popular Color Hunt palettes")
    commands = parser.add_subparsers(dest="command", required=True)

    collect_parser = commands.add_parser("collect", help="refresh the Color Hunt snapshot")
    collect_parser.add_argument("--count", type=int, default=100)
    collect_parser.add_argument("--output", type=Path, default=DEFAULT_DATA)

    match_parser = commands.add_parser("match", help="extract and match an image palette")
    match_parser.add_argument("image", type=Path)
    match_parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    match_parser.add_argument("--top", type=int, default=5)
    match_parser.add_argument("--colors", type=int, default=4)
    match_parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "collect":
        output = collect(args.output, args.count)
        print(f"Saved {args.count} palettes to {output}")
        return

    extracted = extract_dominant_colors(args.image, n_colors=args.colors)
    matches = find_similar_palettes(extracted, args.data, top_n=args.top)
    result = {
        "image": str(args.image),
        "extracted": [
            {"hex": color, "proportion": round(weight, 6)}
            for color, weight in zip(extracted.colors, extracted.weights)
        ],
        "matches": [
            {
                "colors": list(match.colors),
                "distance": round(match.distance, 4),
                "likes": match.likes,
                "popularity_rank": match.rank,
                "url": match.source_url,
            }
            for match in matches
        ],
    }
    if args.as_json:
        print(json.dumps(result, indent=2))
        return

    print("Extracted:", "  ".join(f"{x['hex']} ({x['proportion']:.1%})" for x in result["extracted"]))
    print("\nClosest Color Hunt palettes:")
    for index, match in enumerate(result["matches"], start=1):
        print(
            f"{index}. {' '.join(match['colors'])}  ΔE={match['distance']:.2f}  "
            f"{match['url']}"
        )
