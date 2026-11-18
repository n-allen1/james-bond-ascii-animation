# Reference photographs

The project loads these files (first match wins; `.png .jpg .jpeg .webp .avif .bmp .tif`):

| Character | File stem | Developed with (approx. size) |
|---|---|---|
| Daniel Craig, *No Time to Die* close-up | `daniel_craig.*` | AVIF, 1600x800 |
| Craig's final stance (wide shot) | `daniel_craig_full_shot.*` | PNG, 1588x741 |
| Robert Pattinson, Bond announcement portrait | `robert_pattinson.*` | WebP, 1000x667 |

**These images are not included in the repository** (they are copyrighted, and `assets/*.png|jpg|webp|avif`
is git-ignored). Supply your own copies; the framing coordinates in `config/settings.py` were tuned for
images of roughly these sizes and compositions, so other crops may need adjusting (see below). They are used only as
local input; this project does not download or redistribute any imagery.
`python main.py --placeholder` runs with abstract stand-ins instead (not likenesses).

## Provenance / further reference (not downloaded)
- Pattinson announcement imagery: https://www.aboutamazon.com/news/entertainment/james-bond-robert-pattinson-cast-amazon-mgm-film
- The wide shot uses the supplied film still directly (as a reference, processed into braille characters); nothing is
  invented or attached to Craig's head.

## Swapping or re-framing a photo
Edit `config/settings.py -> PORTRAITS`. Coordinates are fractions of the image (0..1).
Run `python main.py --preview craig --guides` to see the eye (cyan +), face centre (yellow +)
and face-width ellipse drawn over the processed photo.
