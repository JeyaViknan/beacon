// Find the private-use code point of each SF Symbol in the SF Symbols app's font.
//
//   swiftc -O match.swift -o match && ./match <SFSymbolsFallback.otf> checkmark.circle.fill gearshape.fill ...
//
// The font has no name -> code point table, so each symbol is drawn twice: once by name
// (AppKit's NSImage(systemSymbolName:)), once per glyph in the font. Both are drawn at the same
// size, cropped to their ink and shrunk into the same small grid; the closest glyph wins.
// Prints JSON: {"name": {"cp": 1048577, "score": 0.01, "runnerUp": 0.2}}.

import AppKit
import CoreText

let side = 128  // drawing size, px
let grid = 32   // comparison grid, cells

/// Draw into an RGBA bitmap and return the alpha byte per pixel (a black template image and
/// a filled path count alike). Row 0 is the top of the picture.
func coverage(_ draw: (CGContext) -> Void) -> [UInt8] {
    var rgba = [UInt8](repeating: 0, count: side * side * 4)
    let ctx = CGContext(
        data: &rgba, width: side, height: side, bitsPerComponent: 8, bytesPerRow: side * 4,
        space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
    draw(ctx)
    return (0..<(side * side)).map { rgba[$0 * 4 + 3] }
}

/// Crop to the ink, fit it (aspect kept, centred) into the grid and average each cell.
func normalize(_ alpha: [UInt8]) -> [Float]? {
    var minX = side, minY = side, maxX = -1, maxY = -1
    for y in 0..<side {
        for x in 0..<side where alpha[y * side + x] > 16 {
            minX = min(minX, x); maxX = max(maxX, x)
            minY = min(minY, y); maxY = max(maxY, y)
        }
    }
    guard maxX >= 0 else { return nil }
    let w = Double(maxX - minX + 1), h = Double(maxY - minY + 1)
    let cell = max(w, h) / Double(grid)  // source px per grid cell
    let offX = Double(minX) - (Double(grid) * cell - w) / 2
    let offY = Double(minY) - (Double(grid) * cell - h) / 2
    var out = [Float](repeating: 0, count: grid * grid)
    for gy in 0..<grid {
        for gx in 0..<grid {
            let x0 = offX + Double(gx) * cell, y0 = offY + Double(gy) * cell
            var sum = 0.0, n = 0.0
            var y = Int(y0.rounded(.down))
            while Double(y) < y0 + cell {
                var x = Int(x0.rounded(.down))
                while Double(x) < x0 + cell {
                    if x >= 0, x < side, y >= 0, y < side { sum += Double(alpha[y * side + x]) }
                    n += 1
                    x += 1
                }
                y += 1
            }
            out[gy * grid + gx] = Float(sum / max(n, 1) / 255)
        }
    }
    return out
}

let args = CommandLine.arguments
guard args.count >= 3 else {
    FileHandle.standardError.write("usage: match <font.otf> <symbol name>...\n".data(using: .utf8)!)
    exit(2)
}
guard let descriptors = CTFontManagerCreateFontDescriptorsFromURL(URL(fileURLWithPath: args[1]) as CFURL) as? [CTFontDescriptor],
      let descriptor = descriptors.first
else {
    FileHandle.standardError.write("cannot read \(args[1])\n".data(using: .utf8)!)
    exit(1)
}
// Regular weight, like NSImage's symbols ('wght' axis, tag 0x77676874).
let regular = CTFontDescriptorCreateCopyWithAttributes(
    descriptor, [kCTFontVariationAttribute: [0x7767_6874: 400]] as CFDictionary)
let font = CTFontCreateWithFontDescriptor(regular, 100, nil)

// Every glyph in Supplementary Private Use Area-B, drawn once.
var candidates: [(cp: UInt32, bits: [Float])] = []
for cp in UInt32(0x100000)...UInt32(0x10FFFD) {
    let units = Array(String(UnicodeScalar(cp)!).utf16)
    var glyphs = [CGGlyph](repeating: 0, count: units.count)
    guard CTFontGetGlyphsForCharacters(font, units, &glyphs, units.count), glyphs[0] != 0,
          let path = CTFontCreatePathForGlyph(font, glyphs[0], nil)
    else { continue }
    let box = path.boundingBoxOfPath
    guard box.width > 0, box.height > 0 else { continue }
    let alpha = coverage { ctx in
        let scale = CGFloat(side - 8) / max(box.width, box.height)
        ctx.translateBy(x: CGFloat(side) / 2, y: CGFloat(side) / 2)
        ctx.scaleBy(x: scale, y: scale)
        ctx.translateBy(x: -box.midX, y: -box.midY)
        ctx.addPath(path)
        ctx.setFillColor(gray: 0, alpha: 1)
        ctx.fillPath()
    }
    if let bits = normalize(alpha) { candidates.append((cp, bits)) }
}

var out: [String: [String: Double]] = [:]
for name in args.dropFirst(2) {
    guard let base = NSImage(systemSymbolName: name, accessibilityDescription: nil),
          let image = base.withSymbolConfiguration(.init(pointSize: 72, weight: .regular)),
          let target = normalize(coverage { ctx in
              // Aspect-fit the image's frame into the canvas.
              let s = image.size, k = CGFloat(side - 8) / max(s.width, s.height)
              let rect = CGRect(x: (CGFloat(side) - s.width * k) / 2, y: (CGFloat(side) - s.height * k) / 2,
                                width: s.width * k, height: s.height * k)
              NSGraphicsContext.current = NSGraphicsContext(cgContext: ctx, flipped: false)
              image.draw(in: rect)
              NSGraphicsContext.current = nil
          })
    else {
        FileHandle.standardError.write("no such symbol: \(name)\n".data(using: .utf8)!)
        exit(1)
    }
    var scores: [(cp: UInt32, d: Float)] = candidates.map { c in
        var d: Float = 0
        for i in 0..<target.count { d += abs(target[i] - c.bits[i]) }
        return (c.cp, d / Float(grid * grid))
    }
    scores.sort { $0.d < $1.d }
    out[name] = ["cp": Double(scores[0].cp), "score": Double(scores[0].d), "runnerUp": Double(scores[1].d)]
}
let json = try! JSONSerialization.data(withJSONObject: out, options: [.sortedKeys])
print(String(data: json, encoding: .utf8)!)
