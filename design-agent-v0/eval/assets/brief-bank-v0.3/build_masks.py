#!/usr/bin/env python3
"""Build deterministic edit masks for the project-owned Reddit fixtures."""

from pathlib import Path

from PIL import Image, ImageDraw


HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "reddit-fixtures"


def speech_bubble_mask() -> None:
    source = Image.open(FIXTURES / "robot-speech-bubble-source.png")
    mask = Image.new("L", source.size, 0)
    draw = ImageDraw.Draw(mask)
    # Generous region around the generated bubble, including its pointer.
    draw.ellipse((32, 35, 675, 470), fill=255)
    draw.polygon([(425, 405), (575, 520), (535, 390)], fill=255)
    mask.save(FIXTURES / "robot-speech-bubble-mask.png")


def road_surface_mask() -> None:
    source = Image.open(FIXTURES / "australian-empty-road.png")
    mask = Image.new("L", source.size, 0)
    draw = ImageDraw.Draw(mask)
    # Editable road surface; landscape and signs remain protected context.
    draw.polygon(
        [(365, 218), (505, 218), (1535, 800), (1535, 1023), (0, 1023), (300, 610)],
        fill=255,
    )
    mask.save(FIXTURES / "australian-road-edit-mask.png")


if __name__ == "__main__":
    speech_bubble_mask()
    road_surface_mask()
