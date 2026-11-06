"""Regenerate original WebP figures from the example ledgers."""
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from roi import ledger, read_case

INK = "#183142"
TEXT = "#3d5965"
GRID = "#d8e5e8"
CASH = "#116957"
PV = "#365e9f"
BG = "#f7fbfc"


def font(n, bold=False):
    return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", n)


def figure(name, title, subtitle, low, high, ticks, bars=False):
    rows = list(ledger(read_case(HERE.parent / "examples" / (name + ".json"))))
    im = Image.new("RGB", (1000, 610), BG)
    d = ImageDraw.Draw(im)
    d.text((56, 30), title, font=font(40, True), fill=INK)
    d.text((58, 93), subtitle, font=font(25), fill=TEXT)
    d.text((58, 150), "Currency units (thousands)", font=font(22, True), fill=TEXT)
    x = lambda n: 180 + 175*n
    y = lambda v: 475 - (float(v)/1000-low)/(high-low)*286
    for tick in ticks:
        y0 = y(tick*1000)
        d.line(((117, y0), (935, y0)), fill=INK if tick==0 else GRID, width=3 if tick==0 else 2)
        d.text((107, y0), str(tick), anchor="rm", font=font(21), fill=TEXT)
    for r in rows:
        d.text((x(r.year), 502), f"Year {r.year}", anchor="mt", font=font(22), fill=TEXT)
    for color, label, off, attr in (
        (CASH, "Cash", -1, "cash" if bars else "cumulative_cash"),
        (PV, "Discounted", 1, "present_value" if bars else "cumulative_present"),
    ):
        xy = [(x(r.year), y(getattr(r, attr))) for r in rows]
        if bars:
            for px, py in xy:
                px += off*22
                d.rectangle((px-17, min(py,y(0)), px+17, max(py,y(0))), fill=color)
        else:
            d.line(xy, fill=color, width=6)
            for px,py in xy:
                if off < 0:
                    d.ellipse((px-7,py-7,px+7,py+7),fill=color)
                else:
                    d.rectangle((px-6,py-6,px+6,py+6),fill=color)
        key = 343 if off<0 else 533
        d.rectangle((key, 558, key+19, 577), fill=color)
        d.text((key+30, 552), label, font=font(24, True), fill=INK)
    return im


def main():
    figure("steady", "Discount each year separately",
           "Steady case · time zero is the installed cost",
           -100, 50, (-100,-75,-50,-25,0,25,50), True).save(
        HERE / "automation-roi-discounted-cash.webp", "WEBP", lossless=True, method=6)
    figure("late-rebuild", "Payback can reverse",
           "Late rebuild case · cumulative balances",
           -40, 20, (-40,-30,-20,-10,0,10,20)).save(
        HERE / "automation-roi-payback-reversal.webp", "WEBP", lossless=True, method=6)


if __name__ == "__main__":
    main()
