"""Samples
"""

from __future__ import annotations

import random
from pathlib import Path

import piexif
from PIL import Image, ImageDraw, ImageFont, ImageOps

FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/System/Library/Fonts/Supplemental"]
FONT_FILES = {
    "serif": ["DejaVuSerif.ttf", "Georgia.ttf"],
    "serif-italic": ["DejaVuSerif-Italic.ttf", "Georgia Italic.ttf"],
    "mono": ["DejaVuSansMono.ttf", "Courier New.ttf"],
    "sans": ["DejaVuSans.ttf", "Arial.ttf"],
}

TRANSLATION_DELIMITER = "======== ENGLISH TRANSLATION ========"

PLACES = {
    "Lindqvist farm": (45.3600, -92.8500),
    "Foshay Tower": (44.9744, -93.2717),
    "Center City": (45.3939, -92.8166),
    "Minneapolis": (44.9778, -93.2650),
    "Vimmerby": (57.6656, 15.8553),
    "Ellis Island": (40.6995, -74.0396),
}


def font(size: int, style: str = "serif") -> ImageFont.FreeTypeFont:
    for d in FONT_DIRS:
        for name in FONT_FILES[style]:
            p = Path(d) / name
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size=size)


def _noise(size: tuple[int, int], sigma: float, seed: int) -> Image.Image:
    random.seed(seed)
    return Image.effect_noise(size, sigma)


def paper(w: int, h: int, tone=(236, 226, 200), seed: int = 0) -> Image.Image:
    """Aged paper: tinted noise, darker edges, a faint border"""
    base = Image.new("RGB", (w, h), tone)
    grain = ImageOps.colorize(_noise((w, h), 14, seed), black=(150, 130, 95), white=(250, 245, 230))
    img = Image.blend(base, grain, 0.45)
    vignette = Image.radial_gradient("L").resize((w, h)).point(lambda v: int(v * 0.30))
    img = Image.composite(Image.new("RGB", (w, h), (110, 90, 60)), img, vignette)
    d = ImageDraw.Draw(img)
    d.rectangle([12, 12, w - 13, h - 13], outline=(120, 100, 70), width=2)
    return img


def typed(img: Image.Image, lines: list[str], x: int, y: int, size: int = 30,
          style: str = "mono", leading: float = 1.55, ink=(45, 35, 30), seed: int = 1) -> int:
    random.seed(seed)
    d = ImageDraw.Draw(img)
    f = font(size, style)
    step = int(size * leading)
    for line in lines:
        if line.startswith("##"):
            f2 = font(int(size * 1.4), "serif")
            d.text((x + random.randint(-1, 1), y), line[2:].strip(), font=f2, fill=ink)
            y += int(step * 1.6)
            continue
        shade = tuple(min(255, c + random.randint(0, 40)) for c in ink)
        d.text((x + random.randint(-1, 1), y + random.randint(-1, 1)), line, font=f, fill=shade)
        y += step
    return y


def rule(img: Image.Image, y: int, x0: int, x1: int, ink=(90, 75, 55)) -> None:
    ImageDraw.Draw(img).line([x0, y, x1, y], fill=ink, width=2)


# ----------------------------------------------------------------- documents

def birth_record() -> Image.Image:
    img = paper(1240, 1754, seed=11)
    y = typed(img, ["## Vimmerby församling, Kalmar län",
                    "Utdrag ur födelse- och dopboken för år 1868"], 110, 120, 34, "serif", seed=2)
    rule(img, y + 10, 100, 1140)
    y = typed(img, [
        "",
        "N:o 23.",
        "Född den 14 mars 1868, döpt den 22 mars.",
        "Barnets namn:  Anders Johan.",
        "",
        "Föräldrar:  hemmansägaren Johan Petter Nilsson",
        "  Lindqvist och hans hustru Anna Stina",
        "  Andersdotter i Gissemåla, modern 31 år.",
        "",
        "Faddrar:  drängen Nils Johansson och pigan",
        "  Brita Lena Persdotter, båda i Gissemåla.",
        "",
        "Dopförrättare:  komminister C. A. Sandell.",
    ], 110, y + 40, 30, "mono", seed=3)
    rule(img, y + 30, 100, 1140)
    typed(img, ["Rätt utdraget intygar", "", "Vimmerby den 9 juni 1889", "",
                "_______________________", "Kyrkoherde"],
          640, 1380, 26, "serif-italic", seed=4)
    return img


BIRTH_CONTENT = f"""Vimmerby församling, Kalmar län
Utdrag ur födelse- och dopboken för år 1868

N:o 23.
Född den 14 mars 1868, döpt den 22 mars.
Barnets namn: Anders Johan.
Föräldrar: hemmansägaren Johan Petter Nilsson Lindqvist och hans hustru Anna Stina Andersdotter i Gissemåla, modern 31 år.
Faddrar: drängen Nils Johansson och pigan Brita Lena Persdotter, båda i Gissemåla.
Dopförrättare: komminister C. A. Sandell.
Rätt utdraget intygar, Vimmerby den 9 juni 1889.
{TRANSLATION_DELIMITER}
Vimmerby parish, Kalmar county
Extract from the register of births and baptisms for the year 1868

No. 23.
Born 14 March 1868, baptised 22 March.
Child's name: Anders Johan.
Parents: the farm owner Johan Petter Nilsson Lindqvist and his wife Anna Stina Andersdotter of Gissemåla, the mother aged 31.
Sponsors: the farmhand Nils Johansson and the maid Brita Lena Persdotter, both of Gissemåla.
Officiating: curate C. A. Sandell.
Certified a true extract, Vimmerby, 9 June 1889."""


LETTER_P1 = [
    "Center City, Minn.",
    "April 2nd, 1931",
    "",
    "Dear Elsa,",
    "",
    "The ice went out of the lake on Sunday and",
    "Papa says it is the earliest he can remember.",
    "Karl drove up from the city in the Ford and",
    "took a photograph of us all in front of the",
    "house, so you will get one when they are",
    "printed. Oskar has the north field plowed",
    "already and is talking of putting in more",
    "corn this year instead of oats.",
    "",
    "I was glad to hear that Ruth is over her",
    "cold. Tell Harold that Grandpa has a new",
    "calf named after him, which he did not ask",
    "for but there it is.",
]
LETTER_P2 = [
    "We will come down for Decoration Day",
    "if the roads are good. Papa wants to",
    "see the new tower Karl keeps writing",
    "about, though he says nothing that",
    "tall can be safe.",
    "",
    "Give my love to John and the children.",
    "",
    "Your loving Mother,",
    "",
    "Maria Lindqvist",
    "",
    "P.S. Send Oskar's shirts back when",
    "you have a chance, he only has the",
    "two now.",
]
LETTER_CONTENT = "\n".join(LETTER_P1 + [""] + LETTER_P2)


def letter_pages() -> list[Image.Image]:
    p1 = paper(1240, 1754, tone=(240, 233, 214), seed=21)
    typed(p1, LETTER_P1, 140, 150, 34, "serif-italic", leading=1.7, ink=(40, 45, 80), seed=5)
    p2 = paper(1000, 1754, tone=(240, 233, 214), seed=22)
    typed(p2, LETTER_P2, 110, 150, 34, "serif-italic", leading=1.7, ink=(40, 45, 80), seed=6)
    return [p1, p2]


def census_page() -> Image.Image:
    img = paper(2200, 1500, tone=(228, 218, 190), seed=31)
    typed(img, ["## THIRTEENTH CENSUS OF THE UNITED STATES: 1910 — POPULATION",
                "State: Minnesota    County: Chisago    Township: Center City    E.D. No. 47    Sheet 4 B",
                "Enumerated by me on the 21st day of April, 1910.    A. G. Nordlund, Enumerator"],
          80, 60, 26, "serif", seed=7)
    cols = [80, 200, 620, 820, 900, 980, 1120, 1520, 1760, 2120]
    hdr = ["Dwell.", "Name of each person", "Relation", "Sex", "Age", "Marital", "Place of birth", "Immig.", "Occupation"]
    y0 = 260
    d = ImageDraw.Draw(img)
    for x in cols:
        d.line([x, y0, x, 1420], fill=(90, 75, 55), width=2)
    for i in range(0, 25):
        d.line([cols[0], y0 + i * 46, cols[-1], y0 + i * 46], fill=(120, 105, 80), width=1)
    f = font(22, "sans")
    for x, t in zip(cols, hdr):
        d.text((x + 8, y0 + 10), t, font=f, fill=(60, 50, 40))
    rows = [
        ["71", "Lindqvist, Anders", "Head", "M", "42", "M", "Sweden", "1889", "Farmer"],
        ["", "----- Maria", "Wife", "F", "37", "M", "Sweden", "1891", "None"],
        ["", "----- Karl", "Son", "M", "15", "S", "Minnesota", "", "Farm laborer"],
        ["", "----- Elsa", "Daughter", "F", "11", "S", "Minnesota", "", "None"],
        ["", "----- Oskar", "Son", "M", "8", "S", "Minnesota", "", "None"],
        ["72", "Swanson, Peter", "Head", "M", "61", "Wd", "Sweden", "1868", "Farmer"],
        ["", "----- Hilda", "Daughter", "F", "24", "S", "Minnesota", "", "Teacher"],
    ]
    fm = font(24, "mono")
    for r, row in enumerate(rows):
        for x, t in zip(cols, row):
            d.text((x + 8, y0 + 58 + r * 46), t, font=fm, fill=(45, 40, 60))
    return img


def deed_page() -> Image.Image:
    img = paper(1240, 1754, tone=(232, 224, 205), seed=41)
    typed(img, ["## WARRANTY DEED"], 420, 120, 36, "serif", seed=8)
    typed(img, [
        "This Indenture, made this first day of October",
        "in the year of our Lord one thousand eight hundred",
        "and ninety-three, between Peter Swanson, widower,",
        "of the County of Chisago and State of Minnesota,",
        "party of the first part, and Anders Lindqvist of",
        "the same County and State, party of the second part,",
        "",
        "Witnesseth, that the said party of the first part,",
        "for and in consideration of the sum of Six Hundred",
        "Dollars, does hereby grant, bargain, sell and",
        "convey unto the said party of the second part the",
        "north-east quarter of the south-west quarter of",
        "Section fourteen, Township thirty-four north, of",
        "Range twenty-one west, containing forty acres,",
        "more or less, according to the Government survey.",
        "",
        "In Witness Whereof the said party of the first",
        "part has hereunto set his hand and seal.",
        "",
        "            Peter Swanson        [seal]",
        "",
        "Filed for record Oct. 4, 1893, at 10 o'clock A.M.",
        "Book 31 of Deeds, page 288.   J. Lindstrom, Register.",
    ], 120, 220, 28, "serif", leading=1.6, seed=9)
    return img


def receipt_page() -> Image.Image:
    img = paper(700, 1200, tone=(250, 250, 248), seed=51)
    typed(img, ["## NORTH STAR HARDWARE", "Center City, MN", "06/30/2024  10:41", "",
                "2 x 1/2in hex bolt         2.98", "1 x wood screws #8 100ct   7.49",
                "1 x sandpaper 120 asst     3.90", "", "SUBTOTAL                  14.37",
                "TAX                        1.07", "TOTAL                     15.44", "",
                "CARD ****4412", "THANK YOU"], 60, 80, 26, "mono", seed=10)
    return img


# -------------------------------------------------------------------- pics

def _scene(w: int, h: int, kind: str, seed: int) -> Image.Image:
    random.seed(seed)
    img = Image.new("RGB", (w, h), (215, 205, 180))
    d = ImageDraw.Draw(img)
    horizon = int(h * 0.62)
    for y in range(0, horizon):  # sky
        t = y / horizon
        d.line([0, y, w, y], fill=(int(225 - 40 * t), int(220 - 45 * t), int(200 - 50 * t)))
    d.rectangle([0, horizon, w, h], fill=(120, 110, 80))
    if kind == "farm":
        d.rectangle([w * 0.18, horizon - h * 0.22, w * 0.46, horizon + h * 0.02], fill=(70, 60, 50))
        d.polygon([(w * 0.15, horizon - h * 0.22), (w * 0.32, horizon - h * 0.36), (w * 0.49, horizon - h * 0.22)], fill=(50, 42, 36))
        d.rectangle([w * 0.58, horizon - h * 0.16, w * 0.85, horizon + h * 0.02], fill=(85, 70, 55))
        for i in range(12):
            x = w * 0.05 + i * (w * 0.9 / 12)
            d.line([x, horizon + h * 0.08, x, horizon + h * 0.2], fill=(60, 50, 40), width=6)
        d.line([0, horizon + h * 0.12, w, horizon + h * 0.12], fill=(60, 50, 40), width=5)
        for cx, cy, r in [(w * 0.08, horizon - h * 0.05, h * 0.12), (w * 0.93, horizon - h * 0.08, h * 0.15)]:
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(75, 80, 55))
    elif kind == "tower":
        d.rectangle([w * 0.38, h * 0.08, w * 0.62, horizon + h * 0.05], fill=(95, 85, 75))
        d.polygon([(w * 0.38, h * 0.08), (w * 0.5, h * 0.02), (w * 0.62, h * 0.08)], fill=(70, 60, 55))
        for r in range(6, 60, 3):
            for c in (0.41, 0.47, 0.53):
                d.rectangle([w * c, h * r / 100, w * (c + 0.04), h * (r + 1.5) / 100], fill=(140, 130, 115))
        d.rectangle([0, horizon, w, h], fill=(90, 85, 80))
    elif kind == "parlor":
        d.rectangle([0, 0, w, h], fill=(150, 130, 100))
        d.rectangle([w * 0.1, h * 0.15, w * 0.9, h * 0.85], fill=(120, 100, 75))
        d.ellipse([w * 0.3, h * 0.3, w * 0.7, h * 0.7], fill=(60, 50, 45))
    elif kind == "tree":
        d.rectangle([0, 0, w, h], fill=(120, 110, 90))
        d.polygon([(w * 0.5, h * 0.1), (w * 0.2, h * 0.75), (w * 0.8, h * 0.75)], fill=(60, 70, 50))
        for _ in range(30):
            x, y = random.randint(int(w * 0.25), int(w * 0.75)), random.randint(int(h * 0.2), int(h * 0.7))
            d.ellipse([x - 8, y - 8, x + 8, y + 8], fill=(200, 190, 150))
    return img


def photo(w: int, h: int, kind: str, caption: str, seed: int, raw: bool = False) -> Image.Image:
    img = _scene(w, h, kind, seed)
    img = ImageOps.colorize(img.convert("L"), black=(48, 32, 18), white=(246, 236, 210))
    grain = ImageOps.colorize(_noise((w, h), 22 if raw else 12, seed), black=(0, 0, 0), white=(255, 255, 255))
    img = Image.blend(img, grain, 0.22 if raw else 0.12)
    vignette = Image.radial_gradient("L").resize((w, h)).point(lambda v: int(v * (0.55 if raw else 0.35)))
    img = Image.composite(Image.new("RGB", (w, h), (30, 20, 10)), img, vignette)
    if raw:
        img = ImageOps.autocontrast(img, cutoff=0).rotate(1.6, resample=Image.BICUBIC, fillcolor=(120, 110, 95))
        img = Image.blend(img, Image.new("RGB", (w, h), (200, 170, 110)), 0.25)
    border = int(min(w, h) * 0.05)
    card = Image.new("RGB", (w + 2 * border, h + 2 * border + int(border * 1.4)), (238, 232, 218))
    card.paste(img, (border, border))
    ImageDraw.Draw(card).text((border, h + border + int(border * 0.3)), caption,
                              font=font(int(border * 0.8), "serif-italic"), fill=(60, 50, 90))
    return card


def _dms(value: float) -> tuple:
    value = abs(value)
    deg = int(value)
    minutes = int((value - deg) * 60)
    seconds = round(((value - deg) * 60 - minutes) * 60 * 1000)
    return ((deg, 1), (minutes, 1), (seconds, 1000))


def exif_bytes(when: str, description: str | None, gps: tuple[float, float] | None) -> bytes:
    zeroth = {piexif.ImageIFD.Make: b"Bifrost dev", piexif.ImageIFD.Model: b"sample generator",
              piexif.ImageIFD.DateTime: when.encode(), piexif.ImageIFD.Software: b"dev/seed/samples.py"}
    if description:
        zeroth[piexif.ImageIFD.ImageDescription] = description.encode("utf-8")
    exif = {piexif.ExifIFD.DateTimeOriginal: when.encode(), piexif.ExifIFD.DateTimeDigitized: when.encode()}
    gps_ifd = {}
    if gps:
        lat, lon = gps
        gps_ifd = {piexif.GPSIFD.GPSVersionID: (2, 3, 0, 0),
                   piexif.GPSIFD.GPSLatitudeRef: b"N" if lat >= 0 else b"S",
                   piexif.GPSIFD.GPSLatitude: _dms(lat),
                   piexif.GPSIFD.GPSLongitudeRef: b"E" if lon >= 0 else b"W",
                   piexif.GPSIFD.GPSLongitude: _dms(lon)}
    return piexif.dump({"0th": zeroth, "Exif": exif, "GPS": gps_ifd})


# --------------------------------------------------------------------- specs

def generate(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)

    def save_jpeg(img: Image.Image, name: str, quality: int = 82, exif: bytes | None = None) -> Path:
        p = out / name
        if not p.exists():
            kw = {"quality": quality}
            if exif:
                kw["exif"] = exif
            img.save(p, "JPEG", **kw)
        return p

    def save_pdf(pages: list[Image.Image], name: str, dpi: int = 150) -> Path:
        p = out / name
        if not p.exists():
            pages[0].save(p, "PDF", save_all=True, append_images=pages[1:], resolution=dpi)
        return p

    documents = [
        dict(path=save_jpeg(birth_record(), "birth-record-1868.jpg"),
             title="Anders Lindqvist birth record 1868",
             created="1868-03-14", qualifier="Exact", tags=["doc", "transcription"],
             content=BIRTH_CONTENT),
        dict(path=save_pdf(letter_pages(), "letter-maria-to-elsa-1931.pdf"),
             title="Letter from Maria Lindqvist to Elsa Peterson, spring 1931",
             created="1931-04-02", qualifier="Circa", tags=["doc", "transcription", "Gemini OCR"],
             content=LETTER_CONTENT),
        dict(path=save_pdf([census_page()], "census-1910-lindqvist.pdf"),
             title="Lindqvist household 1910",
             created="1910-04-21", qualifier="Year only", tags=["doc"], content=None),
        dict(path=save_jpeg(photo(1400, 1000, "parlor", "Anders & Maria, wedding day 1894", 61), "wedding-portrait-1894.jpg"),
             title="Wedding portrait, Anders and Maria Lindqvist",
             created="1894-05-20", qualifier="Decade only", tags=["img"], content=None),
        dict(path=save_pdf([deed_page()], "warranty-deed-1893.pdf"),
             title="Warranty deed, Peter Swanson to Anders Lindqvist, Chisago County",
             created="1893-10-04", qualifier="Before", tags=["doc"], content=None),
        dict(path=save_pdf([receipt_page()], "hardware-receipt-2024.pdf"),
             title="North Star Hardware receipt",
             created="2024-06-30", qualifier=None, tags=[], content=None),
    ]

    farm, tower = PLACES["Lindqvist farm"], PLACES["Foshay Tower"]
    photos = [
        dict(name="lindqvist-farm-1923.jpg", when="1923:06:15 10:30:00", gps=farm,
             description="The Lindqvist farm near Chisago Lake, summer 1923",
             tags=["Sync/Gramps", "Sync/Date", "Sync/Location", "Sync/Description", "Date/Approximate"],
             account="owner", image=lambda: photo(1600, 1100, "farm", "The farm, summer 1923", 71)),
        dict(name="lindqvist-farm-1923-raw-scan.jpg", when="1923:06:15 10:30:00", gps=None,
             description="Unrestored scan of the 1923 farm photograph",
             tags=[], account="owner", stack_under="lindqvist-farm-1923.jpg",
             image=lambda: photo(1600, 1100, "farm", "The farm, summer 1923", 71, raw=True)),
        dict(name="wedding-1894.jpg", when="1894:05:20 12:00:00", gps=None,
             description="Anders and Maria Lindqvist on their wedding day",
             tags=["Sync/Gramps", "Sync/Date", "Date/Year"],
             account="owner", image=lambda: photo(1000, 1400, "parlor", "Wedding, 1894", 72)),
        dict(name="foshay-tower-1931.jpg", when="1931:08:03 15:10:00", gps=tower,
             description="Karl outside the Foshay Tower, Minneapolis, August 1931",
             tags=["Sync/Gramps", "Sync/Date", "Sync/Location", "Sync/Description"],
             account="owner", image=lambda: photo(1200, 1600, "tower", "Karl, Minneapolis 1931", 73)),
        dict(name="christmas-1948.jpg", when="1948:12:25 17:00:00", gps=None,
             description="Christmas at the Petersons, 1948 (not tagged for sync)",
             tags=[], account="owner", image=lambda: photo(1400, 1000, "tree", "Christmas 1948", 74)),
        dict(name="elsa-about-1920.jpg", when="1920:09:01 12:00:00", gps=None,
             description="Elsa, about 1920 (partner account)",
             tags=["Sync/Gramps", "Sync/Date", "Sync/Description", "Date/Approximate"],
             account="partner", image=lambda: photo(900, 1300, "parlor", "Elsa, about 1920", 75)),
    ]
    for spec in photos:
        spec["path"] = save_jpeg(spec.pop("image")(), spec["name"], quality=86,
                                 exif=exif_bytes(spec["when"], spec["description"], spec["gps"]))
    return {"documents": documents, "photos": photos}
