#import <AppKit/AppKit.h>

int main(void) {
    @autoreleasepool {
        NSString *sourcePath = @"/private/var/folders/l_/05d4s2wx2r553r67w2zvqng40000gn/T/codex-v02-1YLHlo/outputs/v1/mori-night-landing-refinement-v1-self-contained.svg";
        NSString *outputPath = @"/private/var/folders/l_/05d4s2wx2r553r67w2zvqng40000gn/T/codex-v02-1YLHlo/outputs/v1/mori-night-landing-refinement-v1.png";
        NSImage *image = [[NSImage alloc] initWithContentsOfFile:sourcePath];
        if (image == nil) {
            fprintf(stderr, "Unable to load SVG\n");
            return 1;
        }

        NSBitmapImageRep *bitmap = [[NSBitmapImageRep alloc]
            initWithBitmapDataPlanes:NULL
            pixelsWide:1600
            pixelsHigh:960
            bitsPerSample:8
            samplesPerPixel:4
            hasAlpha:YES
            isPlanar:NO
            colorSpaceName:NSDeviceRGBColorSpace
            bytesPerRow:0
            bitsPerPixel:0];
        if (bitmap == nil) {
            fprintf(stderr, "Unable to create bitmap\n");
            return 2;
        }

        [NSGraphicsContext saveGraphicsState];
        NSGraphicsContext *context = [NSGraphicsContext graphicsContextWithBitmapImageRep:bitmap];
        [NSGraphicsContext setCurrentContext:context];
        context.imageInterpolation = NSImageInterpolationHigh;
        [image drawInRect:NSMakeRect(0, 0, 1600, 960)
                 fromRect:NSMakeRect(0, 0, image.size.width, image.size.height)
                operation:NSCompositingOperationCopy
                 fraction:1.0
           respectFlipped:YES
                    hints:nil];
        [context flushGraphics];
        [NSGraphicsContext restoreGraphicsState];

        NSData *png = [bitmap representationUsingType:NSBitmapImageFileTypePNG properties:@{}];
        if (png == nil || ![png writeToFile:outputPath atomically:YES]) {
            fprintf(stderr, "Unable to write PNG\n");
            return 3;
        }
        printf("%s\n", outputPath.UTF8String);
    }
    return 0;
}
