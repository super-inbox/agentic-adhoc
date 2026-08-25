#include <CoreFoundation/CoreFoundation.h>
#include <CoreGraphics/CoreGraphics.h>
#include <ImageIO/ImageIO.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    size_t width;
    size_t height;
    size_t bytes_per_row;
    unsigned char *pixels;
} Raster;

static double row_warmth(const Raster *r, size_t row) {
    const unsigned char *p = r->pixels + row * r->bytes_per_row;
    long long red = 0;
    long long green = 0;
    for (size_t x = 0; x < r->width; x++) {
        red += p[x * 4];
        green += p[x * 4 + 1];
    }
    return (double)(red - green) / (double)r->width;
}

static void reverse_rows(Raster *r) {
    unsigned char *scratch = malloc(r->bytes_per_row);
    if (!scratch) exit(2);
    for (size_t y = 0; y < r->height / 2; y++) {
        unsigned char *top = r->pixels + y * r->bytes_per_row;
        unsigned char *bottom = r->pixels + (r->height - 1 - y) * r->bytes_per_row;
        memcpy(scratch, top, r->bytes_per_row);
        memcpy(top, bottom, r->bytes_per_row);
        memcpy(bottom, scratch, r->bytes_per_row);
    }
    free(scratch);
}

static bool load_rgba(const char *path, Raster *out) {
    CFURLRef url = CFURLCreateFromFileSystemRepresentation(
        kCFAllocatorDefault, (const UInt8 *)path, (CFIndex)strlen(path), false
    );
    if (!url) return false;
    CGImageSourceRef source = CGImageSourceCreateWithURL(url, NULL);
    CFRelease(url);
    if (!source) return false;
    CGImageRef image = CGImageSourceCreateImageAtIndex(source, 0, NULL);
    CFRelease(source);
    if (!image) return false;

    out->width = CGImageGetWidth(image);
    out->height = CGImageGetHeight(image);
    out->bytes_per_row = out->width * 4;
    out->pixels = calloc(out->height, out->bytes_per_row);
    if (!out->pixels) {
        CGImageRelease(image);
        return false;
    }

    CGColorSpaceRef color_space = CGColorSpaceCreateDeviceRGB();
    CGBitmapInfo info = kCGBitmapByteOrder32Big | kCGImageAlphaPremultipliedLast;
    CGContextRef context = CGBitmapContextCreate(
        out->pixels, out->width, out->height, 8, out->bytes_per_row,
        color_space, info
    );
    CGColorSpaceRelease(color_space);
    if (!context) {
        CGImageRelease(image);
        free(out->pixels);
        return false;
    }
    CGContextSetBlendMode(context, kCGBlendModeCopy);
    CGContextSetInterpolationQuality(context, kCGInterpolationNone);
    CGContextDrawImage(context, CGRectMake(0, 0, out->width, out->height), image);
    CGContextRelease(context);
    CGImageRelease(image);

    // Quartz bitmap contexts commonly expose the bottom display row first.
    // Normalize to top-to-bottom rows using the approved terracotta footer as
    // the orientation marker.
    if (row_warmth(out, 0) > row_warmth(out, out->height - 1) + 20.0) {
        reverse_rows(out);
    }
    return true;
}

static bool save_rgba(const char *path, const Raster *r) {
    CFDataRef data = CFDataCreate(
        kCFAllocatorDefault, r->pixels, (CFIndex)(r->bytes_per_row * r->height)
    );
    if (!data) return false;
    CGDataProviderRef provider = CGDataProviderCreateWithCFData(data);
    CFRelease(data);
    if (!provider) return false;
    CGColorSpaceRef color_space = CGColorSpaceCreateDeviceRGB();
    CGBitmapInfo info = kCGBitmapByteOrder32Big | kCGImageAlphaPremultipliedLast;
    CGImageRef image = CGImageCreate(
        r->width, r->height, 8, 32, r->bytes_per_row, color_space, info,
        provider, NULL, false, kCGRenderingIntentDefault
    );
    CGColorSpaceRelease(color_space);
    CGDataProviderRelease(provider);
    if (!image) return false;

    CFURLRef url = CFURLCreateFromFileSystemRepresentation(
        kCFAllocatorDefault, (const UInt8 *)path, (CFIndex)strlen(path), false
    );
    if (!url) {
        CGImageRelease(image);
        return false;
    }
    CGImageDestinationRef destination = CGImageDestinationCreateWithURL(
        url, CFSTR("public.png"), 1, NULL
    );
    CFRelease(url);
    if (!destination) {
        CGImageRelease(image);
        return false;
    }
    CGImageDestinationAddImage(destination, image, NULL);
    bool ok = CGImageDestinationFinalize(destination);
    CFRelease(destination);
    CGImageRelease(image);
    return ok;
}

static double row_difference(const Raster *r, size_t a, size_t b) {
    const unsigned char *row_a = r->pixels + a * r->bytes_per_row;
    const unsigned char *row_b = r->pixels + b * r->bytes_per_row;
    long long total = 0;
    for (size_t x = 0; x < r->width; x++) {
        for (size_t channel = 0; channel < 3; channel++) {
            int delta = (int)row_a[x * 4 + channel] - (int)row_b[x * 4 + channel];
            total += delta < 0 ? -delta : delta;
        }
    }
    return (double)total / (double)(r->width * 3);
}

static size_t strongest_edge(const Raster *r, size_t start, size_t end) {
    size_t best = start;
    double best_score = -1.0;
    for (size_t y = start; y < end; y++) {
        double score = row_difference(r, y - 1, y);
        if (score > best_score) {
            best = y;
            best_score = score;
        }
    }
    return best;
}

static size_t mismatched_pixels(
    const Raster *a, const Raster *b, size_t start_row, size_t end_row
) {
    size_t count = 0;
    for (size_t y = start_row; y < end_row; y++) {
        const unsigned char *row_a = a->pixels + y * a->bytes_per_row;
        const unsigned char *row_b = b->pixels + y * b->bytes_per_row;
        for (size_t x = 0; x < a->width; x++) {
            if (memcmp(row_a + x * 4, row_b + x * 4, 4) != 0) count++;
        }
    }
    return count;
}

int main(int argc, char **argv) {
    const char *root = argc > 1 ? argv[1] : ".";
    char approved_path[2048];
    char edit_path[2048];
    char output_path[2048];
    snprintf(approved_path, sizeof approved_path,
        "%s/outputs/v0/taobao-first-screen-brand-led-v0.png", root);
    snprintf(edit_path, sizeof edit_path,
        "%s/outputs/v1/taobao-first-screen-text-reduced-imagegen-edit-v1.png", root);
    snprintf(output_path, sizeof output_path,
        "%s/outputs/v1/taobao-first-screen-text-reduced-v1.png", root);

    Raster approved = {0};
    Raster edited = {0};
    Raster saved = {0};
    if (!load_rgba(approved_path, &approved) || !load_rgba(edit_path, &edited)) {
        fprintf(stderr, "Could not load input PNG files.\n");
        return 1;
    }
    if (approved.width != edited.width || approved.height != edited.height) {
        fprintf(stderr, "Dimension mismatch.\n");
        return 1;
    }

    size_t panel_top = strongest_edge(&approved, 1040, 1080);
    size_t footer_top = strongest_edge(&approved, 1360, 1410);

    Raster final = approved;
    final.pixels = malloc(approved.bytes_per_row * approved.height);
    if (!final.pixels) return 2;
    memcpy(final.pixels, approved.pixels, approved.bytes_per_row * approved.height);
    for (size_t y = panel_top; y < footer_top; y++) {
        memcpy(
            final.pixels + y * final.bytes_per_row,
            edited.pixels + y * edited.bytes_per_row,
            final.bytes_per_row
        );
    }

    if (!save_rgba(output_path, &final) || !load_rgba(output_path, &saved)) {
        fprintf(stderr, "Could not save or reload output PNG.\n");
        return 1;
    }

    printf("panel_top_y=%zu\n", panel_top);
    printf("footer_top_y=%zu\n", footer_top);
    printf("locked_top_mismatched_pixels=%zu\n",
        mismatched_pixels(&approved, &saved, 0, panel_top));
    printf("locked_footer_mismatched_pixels=%zu\n",
        mismatched_pixels(&approved, &saved, footer_top, approved.height));
    printf("changed_panel_pixels=%zu\n",
        mismatched_pixels(&approved, &saved, panel_top, footer_top));

    free(approved.pixels);
    free(edited.pixels);
    free(final.pixels);
    free(saved.pixels);
    return 0;
}
