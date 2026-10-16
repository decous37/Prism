"""Draw a small native vector prism into the macOS icon sizes."""
from pathlib import Path
import subprocess
import AppKit as A

root = Path(__file__).resolve().parent.parent
folder = root / "build" / "Prism.iconset"
folder.mkdir(parents=True, exist_ok=True)
(root / "resources").mkdir(exist_ok=True)
A.NSApplication.sharedApplication()
for size in (16, 32, 64, 128, 256, 512, 1024):
    image = A.NSImage.alloc().initWithSize_(A.NSMakeSize(size, size))
    image.lockFocus()
    transform = A.NSAffineTransform.transform()
    transform.scaleBy_(size / 1024)
    transform.concat()
    card = A.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(A.NSMakeRect(50, 50, 924, 924), 210, 210)
    A.NSColor.colorWithCalibratedWhite_alpha_(0.98, 1).setFill()
    card.fill()
    triangle = A.NSBezierPath.bezierPath()
    triangle.moveToPoint_((512, 818))
    triangle.lineToPoint_((208, 252))
    triangle.lineToPoint_((816, 252))
    triangle.closePath()
    gradient = A.NSGradient.alloc().initWithStartingColor_endingColor_(
        A.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.22, 0.66, 0.98, 1),
        A.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.47, 0.30, 0.93, 1))
    gradient.drawInBezierPath_angle_(triangle, -45)
    facet = A.NSBezierPath.bezierPath()
    facet.moveToPoint_((512, 818))
    facet.lineToPoint_((512, 252))
    facet.lineToPoint_((816, 252))
    facet.closePath()
    A.NSColor.colorWithCalibratedWhite_alpha_(1, 0.22).setFill()
    facet.fill()
    image.unlockFocus()
    bitmap = A.NSBitmapImageRep.imageRepWithData_(image.TIFFRepresentation())
    data = bitmap.representationUsingType_properties_(A.NSBitmapImageFileTypePNG, {})
    name = f"icon_{size}x{size}.png" if size <= 512 else "icon_512x512@2x.png"
    data.writeToFile_atomically_(str(folder / name), True)
    if size in (32, 64, 256, 512):
        data.writeToFile_atomically_(str(folder / f"icon_{size // 2}x{size // 2}@2x.png"), True)
subprocess.run(["iconutil", "-c", "icns", str(folder), "-o", str(root / "resources" / "Prism.icns")], check=True)
