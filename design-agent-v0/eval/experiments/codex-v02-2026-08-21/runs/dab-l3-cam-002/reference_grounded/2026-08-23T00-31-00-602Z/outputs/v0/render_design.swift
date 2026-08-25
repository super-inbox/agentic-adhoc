import AppKit
import Foundation

// Deterministic renderer for the SUMMER FORM channel adaptations.
// All layout coordinates use a top-left origin; output is exact pixel size.

struct Palette {
    static let paper = NSColor(calibratedRed: 0.949, green: 0.935, blue: 0.890, alpha: 1)
    static let navy = NSColor(calibratedRed: 0.075, green: 0.196, blue: 0.430, alpha: 1)
    static let line = NSColor(calibratedRed: 0.105, green: 0.267, blue: 0.540, alpha: 1)
    static let coral = NSColor(calibratedRed: 0.941, green: 0.340, blue: 0.278, alpha: 1)
    static let previewBackground = NSColor(calibratedRed: 0.875, green: 0.850, blue: 0.800, alpha: 1)
}

struct Canvas {
    let width: Int
    let height: Int
    let rep: NSBitmapImageRep
    let context: NSGraphicsContext

    init(width: Int, height: Int) {
        self.width = width
        self.height = height
        guard let bitmap = NSBitmapImageRep(
            bitmapDataPlanes: nil,
            pixelsWide: width,
            pixelsHigh: height,
            bitsPerSample: 8,
            samplesPerPixel: 4,
            hasAlpha: true,
            isPlanar: false,
            colorSpaceName: .deviceRGB,
            bytesPerRow: 0,
            bitsPerPixel: 0
        ) else {
            fatalError("Could not allocate bitmap")
        }
        bitmap.size = NSSize(width: width, height: height)
        guard let graphics = NSGraphicsContext(bitmapImageRep: bitmap) else {
            fatalError("Could not create graphics context")
        }
        self.rep = bitmap
        self.context = graphics
    }

    func nsRect(_ x: CGFloat, _ y: CGFloat, _ w: CGFloat, _ h: CGFloat) -> NSRect {
        NSRect(x: x, y: CGFloat(height) - y - h, width: w, height: h)
    }

    func point(_ x: CGFloat, _ y: CGFloat) -> NSPoint {
        NSPoint(x: x, y: CGFloat(height) - y)
    }

    func activate() {
        NSGraphicsContext.current = context
        context.shouldAntialias = true
        context.imageInterpolation = .high
    }

    func fill(_ color: NSColor) {
        activate()
        color.setFill()
        NSBezierPath(rect: NSRect(x: 0, y: 0, width: width, height: height)).fill()
    }

    func fillRect(x: CGFloat, y: CGFloat, w: CGFloat, h: CGFloat, color: NSColor) {
        color.setFill()
        NSBezierPath(rect: nsRect(x, y, w, h)).fill()
    }

    func strokeRect(x: CGFloat, y: CGFloat, w: CGFloat, h: CGFloat, color: NSColor = Palette.line, lineWidth: CGFloat = 2.4) {
        color.setStroke()
        let path = NSBezierPath(rect: nsRect(x, y, w, h))
        path.lineWidth = lineWidth
        path.stroke()
    }

    func line(x1: CGFloat, y1: CGFloat, x2: CGFloat, y2: CGFloat, color: NSColor = Palette.line, lineWidth: CGFloat = 2.4) {
        color.setStroke()
        let path = NSBezierPath()
        path.move(to: point(x1, y1))
        path.line(to: point(x2, y2))
        path.lineWidth = lineWidth
        path.stroke()
    }

    func circle(cx: CGFloat, cy: CGFloat, r: CGFloat, stroke: NSColor = Palette.line, fill: NSColor? = nil, lineWidth: CGFloat = 2.4) {
        let rect = nsRect(cx - r, cy - r, r * 2, r * 2)
        let path = NSBezierPath(ovalIn: rect)
        if let fillColor = fill {
            fillColor.setFill()
            path.fill()
        }
        stroke.setStroke()
        path.lineWidth = lineWidth
        path.stroke()
    }

    func clippedCircle(cx: CGFloat, cy: CGFloat, r: CGFloat, clipX: CGFloat, clipY: CGFloat, clipW: CGFloat, clipH: CGFloat, stroke: NSColor = Palette.line, fill: NSColor? = nil, lineWidth: CGFloat = 2.4) {
        NSGraphicsContext.saveGraphicsState()
        NSBezierPath(rect: nsRect(clipX, clipY, clipW, clipH)).addClip()
        circle(cx: cx, cy: cy, r: r, stroke: stroke, fill: fill, lineWidth: lineWidth)
        NSGraphicsContext.restoreGraphicsState()
    }

    func drawImage(path: String, x: CGFloat, y: CGFloat, w: CGFloat, h: CGFloat, opacity: CGFloat = 1) {
        guard let image = NSImage(contentsOfFile: path) else {
            fatalError("Could not load image at \(path)")
        }
        image.draw(
            in: nsRect(x, y, w, h),
            from: NSRect(origin: .zero, size: image.size),
            operation: .sourceOver,
            fraction: opacity,
            respectFlipped: false,
            hints: [.interpolation: NSImageInterpolation.high]
        )
    }

    @discardableResult
    func drawText(_ value: String, x: CGFloat, top: CGFloat, size: CGFloat, bold: Bool, color: NSColor = Palette.navy, tracking: CGFloat = 0) -> NSSize {
        let fontName = bold ? "Arial-BoldMT" : "ArialMT"
        let font = NSFont(name: fontName, size: size) ?? (bold ? NSFont.boldSystemFont(ofSize: size) : NSFont.systemFont(ofSize: size))
        let attrs: [NSAttributedString.Key: Any] = [
            .font: font,
            .foregroundColor: color,
            .kern: tracking
        ]
        let string = value as NSString
        let measured = string.size(withAttributes: attrs)
        string.draw(at: NSPoint(x: x, y: CGFloat(height) - top - measured.height), withAttributes: attrs)
        return measured
    }

    func paperTexture(seed: UInt64, density: Int) {
        var state = seed
        func next() -> UInt64 {
            state = state &* 6364136223846793005 &+ 1442695040888963407
            return state
        }
        for i in 0..<density {
            let x = CGFloat(next() % UInt64(width * 1000)) / 1000
            let y = CGFloat(next() % UInt64(height * 1000)) / 1000
            let len = CGFloat(1 + next() % 5)
            let alpha = CGFloat(8 + next() % 13) / 1000
            let shade = (i % 3 == 0) ? NSColor.white.withAlphaComponent(alpha) : NSColor(calibratedWhite: 0.38, alpha: alpha)
            line(x1: x, y1: y, x2: x + len, y2: y + CGFloat(Int(next() % 3) - 1), color: shade, lineWidth: 0.55)
        }
    }

    func save(_ path: String) {
        guard let data = rep.representation(using: .png, properties: [:]) else {
            fatalError("Could not encode PNG")
        }
        do {
            try data.write(to: URL(fileURLWithPath: path))
        } catch {
            fatalError("Could not write \(path): \(error)")
        }
    }
}

let cwd = FileManager.default.currentDirectoryPath
let out = cwd + "/outputs/v0"
let origami = out + "/assets/origami-approved-tile.png"
let mark = out + "/assets/campaign-mark-approved-tile.png"

func drawWebsite() {
    let c = Canvas(width: 1200, height: 628)
    c.activate()
    c.fill(Palette.paper)
    c.paperTexture(seed: 1200628, density: 2600)

    // 64 px safe frame and approved geometric system.
    c.strokeRect(x: 64, y: 64, w: 1072, h: 500, lineWidth: 2.5)
    c.line(x1: 64, y1: 140, x2: 1136, y2: 140, lineWidth: 2.5)
    c.line(x1: 445, y1: 140, x2: 445, y2: 564, lineWidth: 2.5)
    c.line(x1: 445, y1: 426, x2: 1136, y2: 426, lineWidth: 2.5)
    c.line(x1: 930, y1: 426, x2: 930, y2: 564, lineWidth: 2.5)
    c.line(x1: 235, y1: 64, x2: 235, y2: 140, lineWidth: 2.5)
    c.fillRect(x: 235, y: 106, w: 210, h: 34, color: Palette.coral)
    c.fillRect(x: 900, y: 64, w: 160, h: 76, color: Palette.navy)
    c.fillRect(x: 1060, y: 64, w: 76, h: 76, color: Palette.coral)
    c.fillRect(x: 64, y: 330, w: 116, h: 96, color: Palette.coral)
    c.fillRect(x: 64, y: 470, w: 260, h: 94, color: Palette.navy)
    c.fillRect(x: 445, y: 470, w: 130, h: 94, color: Palette.coral)
    c.fillRect(x: 575, y: 520, w: 70, h: 44, color: Palette.navy)
    c.clippedCircle(cx: 160, cy: 140, r: 96, clipX: 64, clipY: 64, clipW: 171, clipH: 266, lineWidth: 2.5)
    c.circle(cx: 250, cy: 115, r: 54, lineWidth: 2.5)
    c.clippedCircle(cx: 600, cy: 426, r: 136, clipX: 445, clipY: 220, clipW: 300, clipH: 206, lineWidth: 2.5)
    c.clippedCircle(cx: 1136, cy: 376, r: 48, clipX: 1088, clipY: 328, clipW: 48, clipH: 96, stroke: Palette.coral, fill: Palette.coral, lineWidth: 0)

    // Locked source imagery: native 340x380 crop, no stretch and no regeneration.
    c.drawImage(path: origami, x: 92, y: 180, w: 340, h: 380)
    c.drawImage(path: mark, x: 964, y: 438, w: 112, h: 112)

    c.drawText("SUMMER", x: 486, top: 166, size: 105, bold: true, tracking: -1.8)
    c.drawText("FORM", x: 700, top: 273, size: 105, bold: true, tracking: -1.8)
    c.drawText("Design Market", x: 520, top: 439, size: 34, bold: false, tracking: -0.2)
    c.drawText("08—10 AUG", x: 520, top: 480, size: 34, bold: false, tracking: -0.2)
    c.drawText("BROOKLYN", x: 520, top: 521, size: 34, bold: false, tracking: 0.1)

    c.save(out + "/summer-form-website-1200x628.png")
}

func drawInstagram() {
    let c = Canvas(width: 1080, height: 1350)
    c.activate()
    c.fill(Palette.paper)
    c.paperTexture(seed: 10801350, density: 4200)

    c.strokeRect(x: 64, y: 64, w: 952, h: 1222, lineWidth: 2.7)
    c.line(x1: 64, y1: 160, x2: 1016, y2: 160, lineWidth: 2.7)
    c.line(x1: 64, y1: 530, x2: 1016, y2: 530, lineWidth: 2.7)
    c.line(x1: 64, y1: 650, x2: 1016, y2: 650, lineWidth: 2.7)
    c.line(x1: 64, y1: 1085, x2: 1016, y2: 1085, lineWidth: 2.7)
    c.line(x1: 760, y1: 530, x2: 760, y2: 1085, lineWidth: 2.7)
    c.line(x1: 620, y1: 1085, x2: 620, y2: 1286, lineWidth: 2.7)
    c.fillRect(x: 730, y: 64, w: 200, h: 96, color: Palette.navy)
    c.fillRect(x: 930, y: 64, w: 86, h: 96, color: Palette.coral)
    c.fillRect(x: 200, y: 530, w: 560, h: 120, color: Palette.coral)
    c.fillRect(x: 64, y: 860, w: 126, h: 225, color: Palette.coral)
    c.fillRect(x: 64, y: 1015, w: 420, h: 70, color: Palette.navy)
    c.fillRect(x: 620, y: 1085, w: 130, h: 150, color: Palette.coral)
    c.fillRect(x: 620, y: 1235, w: 74, h: 51, color: Palette.navy)
    c.clippedCircle(cx: 160, cy: 160, r: 96, clipX: 64, clipY: 64, clipW: 192, clipH: 192, lineWidth: 2.7)
    c.circle(cx: 160, cy: 590, r: 60, lineWidth: 2.7)
    c.clippedCircle(cx: 760, cy: 1030, r: 190, clipX: 570, clipY: 840, clipW: 190, clipH: 245, lineWidth: 2.7)
    c.clippedCircle(cx: 1016, cy: 1018, r: 52, clipX: 964, clipY: 966, clipW: 52, clipH: 104, stroke: Palette.coral, fill: Palette.coral, lineWidth: 0)
    c.clippedCircle(cx: 64, cy: 1286, r: 48, clipX: 64, clipY: 1238, clipW: 48, clipH: 48, stroke: Palette.coral, fill: Palette.coral, lineWidth: 0)

    // Approved main visual and mark are source crops at preserved aspect ratio.
    c.drawImage(path: origami, x: 205, y: 600, w: 425, h: 475)
    c.drawImage(path: mark, x: 810, y: 1110, w: 160, h: 160)

    c.drawText("SUMMER", x: 90, top: 184, size: 148, bold: true, tracking: -2.6)
    c.drawText("FORM", x: 90, top: 345, size: 158, bold: true, tracking: -2.4)
    c.drawText("Design Market", x: 100, top: 1116, size: 43, bold: false, tracking: -0.2)
    c.drawText("08—10 AUG", x: 100, top: 1171, size: 43, bold: false, tracking: -0.1)
    c.drawText("BROOKLYN", x: 100, top: 1226, size: 43, bold: false, tracking: 0.1)

    c.save(out + "/summer-form-instagram-1080x1350.png")
}

func drawStory() {
    let c = Canvas(width: 1080, height: 1920)
    c.activate()
    c.fill(Palette.paper)
    c.paperTexture(seed: 10801920, density: 6000)

    c.strokeRect(x: 64, y: 64, w: 952, h: 1792, lineWidth: 2.8)
    c.line(x1: 64, y1: 200, x2: 1016, y2: 200, lineWidth: 2.8)
    c.line(x1: 64, y1: 630, x2: 1016, y2: 630, lineWidth: 2.8)
    c.line(x1: 64, y1: 770, x2: 1016, y2: 770, lineWidth: 2.8)
    c.line(x1: 64, y1: 1335, x2: 1016, y2: 1335, lineWidth: 2.8)
    c.line(x1: 64, y1: 1410, x2: 1016, y2: 1410, lineWidth: 2.8)
    c.line(x1: 64, y1: 1735, x2: 1016, y2: 1735, lineWidth: 2.8)
    c.line(x1: 200, y1: 64, x2: 200, y2: 200, lineWidth: 2.8)
    c.line(x1: 780, y1: 630, x2: 780, y2: 1335, lineWidth: 2.8)
    c.line(x1: 560, y1: 1410, x2: 560, y2: 1735, lineWidth: 2.8)
    c.fillRect(x: 710, y: 64, w: 220, h: 136, color: Palette.navy)
    c.fillRect(x: 930, y: 64, w: 86, h: 136, color: Palette.coral)
    c.fillRect(x: 200, y: 630, w: 580, h: 140, color: Palette.coral)
    c.fillRect(x: 64, y: 1020, w: 150, h: 315, color: Palette.coral)
    c.fillRect(x: 64, y: 1335, w: 496, h: 75, color: Palette.navy)
    c.fillRect(x: 560, y: 1410, w: 150, h: 250, color: Palette.coral)
    c.fillRect(x: 560, y: 1660, w: 80, h: 75, color: Palette.navy)
    c.clippedCircle(cx: 160, cy: 200, r: 96, clipX: 64, clipY: 64, clipW: 192, clipH: 192, lineWidth: 2.8)
    c.circle(cx: 160, cy: 700, r: 70, lineWidth: 2.8)
    c.clippedCircle(cx: 780, cy: 1260, r: 245, clipX: 535, clipY: 1015, clipW: 245, clipH: 320, lineWidth: 2.8)
    c.clippedCircle(cx: 64, cy: 1856, r: 70, clipX: 64, clipY: 1786, clipW: 70, clipH: 70, stroke: Palette.coral, fill: Palette.coral, lineWidth: 0)
    c.clippedCircle(cx: 1016, cy: 1856, r: 70, clipX: 946, clipY: 1786, clipW: 70, clipH: 70, stroke: Palette.coral, fill: Palette.coral, lineWidth: 0)
    c.clippedCircle(cx: 540, cy: 1856, r: 145, clipX: 395, clipY: 1735, clipW: 290, clipH: 121, lineWidth: 2.8)

    // Approved main visual and mark are only repositioned and uniformly scaled.
    c.drawImage(path: origami, x: 205, y: 720, w: 540, h: 603.5294)
    c.drawImage(path: mark, x: 770, y: 1470, w: 190, h: 190)

    c.drawText("SUMMER", x: 82, top: 228, size: 150, bold: true, tracking: -2.7)
    c.drawText("FORM", x: 82, top: 394, size: 160, bold: true, tracking: -2.5)
    c.drawText("Design Market", x: 100, top: 1480, size: 50, bold: false, tracking: -0.3)
    c.drawText("08—10 AUG", x: 100, top: 1544, size: 50, bold: false, tracking: -0.2)
    c.drawText("BROOKLYN", x: 100, top: 1608, size: 50, bold: false, tracking: 0.2)

    c.save(out + "/summer-form-story-1080x1920.png")
}

func drawPreview() {
    let websitePath = out + "/summer-form-website-1200x628.png"
    let instagramPath = out + "/summer-form-instagram-1080x1350.png"
    let storyPath = out + "/summer-form-story-1080x1920.png"
    let c = Canvas(width: 2000, height: 1600)
    c.activate()
    c.fill(Palette.previewBackground)

    // Card shadows are preview-only and are not present in channel exports.
    c.fillRect(x: 138, y: 106, w: 1724, h: 904, color: NSColor.black.withAlphaComponent(0.13))
    c.drawImage(path: websitePath, x: 120, y: 88, w: 1720, h: 900.1333)
    c.drawText("WEBSITE · 1200×628", x: 120, top: 28, size: 28, bold: true, color: Palette.navy, tracking: 0.6)

    c.fillRect(x: 288, y: 1068, w: 428, h: 535, color: NSColor.black.withAlphaComponent(0.13))
    c.drawImage(path: instagramPath, x: 270, y: 1050, w: 420, h: 525)
    c.drawText("INSTAGRAM · 1080×1350", x: 270, top: 1000, size: 25, bold: true, color: Palette.navy, tracking: 0.4)

    c.fillRect(x: 894, y: 1068, w: 313.25, h: 553, color: NSColor.black.withAlphaComponent(0.13))
    c.drawImage(path: storyPath, x: 876, y: 1050, w: 303.75, h: 540)
    c.drawText("STORY · 1080×1920", x: 876, top: 1000, size: 25, bold: true, color: Palette.navy, tracking: 0.4)

    c.drawText("APPROVED MASTER ADAPTED — NO NEW KEY VISUAL", x: 1350, top: 1210, size: 24, bold: true, color: Palette.navy, tracking: 0.7)
    c.drawText("Locked: title · date · location · palette · geometry · origami · mark", x: 1350, top: 1260, size: 20, bold: false, color: Palette.navy, tracking: 0.1)
    c.drawText("Editable object documents and machine checks accompany these previews.", x: 1350, top: 1302, size: 20, bold: false, color: Palette.navy, tracking: 0.1)
    c.save(out + "/preview.png")
}

drawWebsite()
drawInstagram()
drawStory()
drawPreview()

