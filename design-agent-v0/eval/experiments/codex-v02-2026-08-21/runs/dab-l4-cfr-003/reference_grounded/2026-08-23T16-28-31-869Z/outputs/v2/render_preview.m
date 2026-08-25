#import <Cocoa/Cocoa.h>

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        if (argc != 3) {
            fprintf(stderr, "usage: render_preview input.svg output.png\n");
            return 64;
        }

        NSString *inputPath = [NSString stringWithUTF8String:argv[1]];
        NSString *outputPath = [NSString stringWithUTF8String:argv[2]];
        NSString *assetDirectory = [inputPath stringByDeletingLastPathComponent];
        NSImage *source = [[NSImage alloc] initWithContentsOfFile:inputPath];
        NSImage *background = [[NSImage alloc] initWithContentsOfFile:
            [assetDirectory stringByAppendingPathComponent:@"ambient_background_v0.png"]];
        NSImage *product = [[NSImage alloc] initWithContentsOfFile:
            [assetDirectory stringByAppendingPathComponent:@"product_reference_locked.png"]];
        if (source == nil) {
            fprintf(stderr, "failed to load SVG\n");
            return 65;
        }
        if (background == nil || product == nil) {
            fprintf(stderr, "failed to load linked raster assets\n");
            return 65;
        }

        const NSInteger width = 1200;
        const NSInteger height = 1600;
        NSBitmapImageRep *bitmap = [[NSBitmapImageRep alloc]
            initWithBitmapDataPlanes:NULL
            pixelsWide:width
            pixelsHigh:height
            bitsPerSample:8
            samplesPerPixel:4
            hasAlpha:YES
            isPlanar:NO
            colorSpaceName:NSDeviceRGBColorSpace
            bytesPerRow:0
            bitsPerPixel:0];
        if (bitmap == nil) {
            fprintf(stderr, "failed to allocate bitmap\n");
            return 66;
        }

        NSGraphicsContext *context = [NSGraphicsContext graphicsContextWithBitmapImageRep:bitmap];
        [NSGraphicsContext saveGraphicsState];
        [NSGraphicsContext setCurrentContext:context];
        context.imageInterpolation = NSImageInterpolationHigh;
        [[NSColor colorWithCalibratedRed:243.0/255.0 green:237.0/255.0 blue:223.0/255.0 alpha:1.0] setFill];
        NSRectFill(NSMakeRect(0, 0, width, height));

        // Draw the generated atmospheric plate first. Crop to the 3:4 canvas
        // ratio so the raster is not stretched.
        CGFloat backgroundCropHeight = background.size.width * 4.0 / 3.0;
        CGFloat backgroundCropY = (background.size.height - backgroundCropHeight) / 2.0;
        [background drawInRect:NSMakeRect(0, 0, width, height)
                      fromRect:NSMakeRect(0, backgroundCropY, background.size.width, backgroundCropHeight)
                     operation:NSCompositingOperationSourceOver
                      fraction:1.0
                respectFlipped:YES
                         hints:@{NSImageHintInterpolation: @(NSImageInterpolationHigh)}];

        [source drawInRect:NSMakeRect(0, 0, width, height)
                 fromRect:NSMakeRect(0, 0, source.size.width, source.size.height)
                operation:NSCompositingOperationSourceOver
                 fraction:1.0
           respectFlipped:YES
                    hints:@{NSImageHintInterpolation: @(NSImageInterpolationHigh)}];

        // Insert the exact locked product raster as its own image object. The
        // source file is never recolored or geometrically distorted.
        [NSGraphicsContext saveGraphicsState];
        NSRect productRect = NSMakeRect(176, height - 92 - 848, 848, 848);
        [[NSBezierPath bezierPathWithRoundedRect:productRect xRadius:22 yRadius:22] addClip];
        [product drawInRect:productRect
                   fromRect:NSMakeRect(0, 0, product.size.width, product.size.height)
                  operation:NSCompositingOperationSourceOver
                   fraction:1.0
             respectFlipped:YES
                      hints:@{NSImageHintInterpolation: @(NSImageInterpolationHigh)}];
        [NSGraphicsContext restoreGraphicsState];

        [context flushGraphics];
        [NSGraphicsContext restoreGraphicsState];

        NSData *png = [bitmap representationUsingType:NSBitmapImageFileTypePNG properties:@{}];
        if (![png writeToFile:outputPath atomically:YES]) {
            fprintf(stderr, "failed to write PNG\n");
            return 67;
        }
    }
    return 0;
}
