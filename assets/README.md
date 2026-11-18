# Reference photographs

The project loads these files (first match wins; `.png .jpg .jpeg .webp .avif .bmp .tif`):

| Character | File stem | Currently in use |
|---|---|---|
| Daniel Craig, *No Time to Die* | `daniel_craig.*` | `daniel_craig.avif` (1600x800) |
| Craig's final stance (wide shot) | `daniel_craig_full_shot.*` | `daniel_craig_full_shot.png` (1588x741) |
| Robert Pattinson, Bond announcement portrait | `robert_pattinson.*` | `robert_pattinson.webp` (1000x667) |

These are the photographs supplied by the project owner. They are used only as local input;
this repository does not download, bundle or redistribute any other imagery.

## Provenance / further reference (not downloaded)
- Pattinson announcement imagery: https://www.aboutamazon.com/news/entertainment/james-bond-robert-pattinson-cast-amazon-mgm-film
- The wide shot uses the supplied film still directly (as a reference, processed into braille characters); nothing is
  invented or attached to Craig's head.

## Swapping or re-framing a photo
Edit `config/settings.py -> PORTRAITS`. Coordinates are fractions of the image (0..1).
Run `python main.py --preview craig --guides` to see the eye (cyan +), face centre (yellow +)
and face-width ellipse drawn over the processed photo.
