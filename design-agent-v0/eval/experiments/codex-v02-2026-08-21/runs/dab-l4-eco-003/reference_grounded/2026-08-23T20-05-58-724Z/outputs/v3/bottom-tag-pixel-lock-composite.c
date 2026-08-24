#include <CoreFoundation/CoreFoundation.h>
#include <CoreGraphics/CoreGraphics.h>
#include <ImageIO/ImageIO.h>
#include <math.h>
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

static double clamp01(double value) {
    if (value < 0.0) return 0.0;
    if (value > 1.0) return 1.0;
    return value;
}

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

static bool is_tag_cream(unsigned char r, unsigned char g, unsigned char b) {
    return r > 195 && g > 155 && b > 115 && r > g && g > b;
}

static double capsule_alpha(
    double x, double y, double center_x, double center_y,
    double half_width, double half_height
) {
    double abs_x = fabs(x - center_x);
    double abs_y = fabs(y - center_y);
    double straight_half = half_width - half_height;
    double signed_distance;

    if (abs_x <= straight_half) {
        signed_distance = abs_y - half_height;
    } else {
        double dx = abs_x - straight_half;
        signed_distance = sqrt(dx * dx + abs_y * abs_y) - half_height;
    }
    return clamp01(0.75 - signed_distance);
}

static size_t mismatch_count_above_row(
    const Raster *base, const Raster *final, size_t end_row
) {
    size_t count = 0;
    for (size_t y = 0; y < end_row; y++) {
        const unsigned char *a = base->pixels + y * base->bytes_per_row;
        const unsigned char *b = final->pixels + y * final->bytes_per_row;
        for (size_t x = 0; x < base->width; x++) {
            if (memcmp(a + x * 4, b + x * 4, 4) != 0) count++;
        }
    }
    return count;
}

static size_t mismatch_count_outside_capsule(
    const Raster *base, const Raster *final,
    double center_x, double center_y, double half_width, double half_height
) {
    size_t count = 0;
    for (size_t y = 0; y < base->height; y++) {
        const unsigned char *a = base->pixels + y * base->bytes_per_row;
        const unsigned char *b = final->pixels + y * final->bytes_per_row;
        for (size_t x = 0; x < base->width; x++) {
            double allowed = capsule_alpha(
                x + 0.5, y + 0.5, center_x, center_y, half_width, half_height
            );
            if (allowed > 0.0) continue;
            if (memcmp(a + x * 4, b + x * 4, 4) != 0) count++;
        }
    }
    return count;
}

int main(int argc, char **argv) {
    const char *root = argc > 1 ? argv[1] : ".";
    char base_path[2048];
    char edit_path[2048];
    char output_path[2048];
    snprintf(base_path, sizeof base_path,
        "%s/outputs/v2/taobao-first-screen-product-color-corrected-v2.png", root);
    snprintf(edit_path, sizeof edit_path,
        "%s/outputs/v3/taobao-first-screen-bottom-tag-imagegen-edit-v3.png", root);
    snprintf(output_path, sizeof output_path,
        "%s/outputs/v3/taobao-first-screen-bottom-tag-v3.png", root);

    Raster base = {0};
    Raster edit = {0};
    Raster saved = {0};
    if (!load_rgba(base_path, &base) || !load_rgba(edit_path, &edit)) {
        fprintf(stderr, "Could not load input PNG files.\n");
        return 1;
    }
    if (base.width != edit.width || base.height != edit.height) {
        fprintf(stderr, "Dimension mismatch.\n");
        return 1;
    }

    size_t min_x = base.width, min_y = base.height, max_x = 0, max_y = 0;
    size_t cream_pixels = 0;
    const size_t footer_top = 1386;
    for (size_t y = footer_top; y < edit.height; y++) {
        const unsigned char *row = edit.pixels + y * edit.bytes_per_row;
        for (size_t x = 0; x < edit.width; x++) {
            const unsigned char *p = row + x * 4;
            if (!is_tag_cream(p[0], p[1], p[2])) continue;
            if (x < min_x) min_x = x;
            if (y < min_y) min_y = y;
            if (x > max_x) max_x = x;
            if (y > max_y) max_y = y;
            cream_pixels++;
        }
    }
    if (cream_pixels == 0) {
        fprintf(stderr, "Could not detect the generated cream tag.\n");
        return 1;
    }

    double center_x = ((double)min_x + (double)max_x + 1.0) / 2.0;
    double center_y = ((double)min_y + (double)max_y + 1.0) / 2.0;
    double half_width = ((double)max_x - (double)min_x + 1.0) / 2.0 + 2.0;
    double half_height = ((double)max_y - (double)min_y + 1.0) / 2.0 + 2.0;

    Raster final = base;
    final.pixels = malloc(base.bytes_per_row * base.height);
    if (!final.pixels) return 2;
    memcpy(final.pixels, base.pixels, base.bytes_per_row * base.height);

    size_t changed_pixels = 0;
    size_t changed_min_x = base.width, changed_min_y = base.height;
    size_t changed_max_x = 0, changed_max_y = 0;
    for (size_t y = footer_top; y < base.height; y++) {
        unsigned char *out_row = final.pixels + y * final.bytes_per_row;
        const unsigned char *edit_row = edit.pixels + y * edit.bytes_per_row;
        for (size_t x = 0; x < base.width; x++) {
            double alpha = capsule_alpha(
                x + 0.5, y + 0.5, center_x, center_y, half_width, half_height
            );
            if (alpha <= 0.0) continue;
            unsigned char *out = out_row + x * 4;
            const unsigned char *src = edit_row + x * 4;
            unsigned char before[4] = {out[0], out[1], out[2], out[3]};
            for (size_t channel = 0; channel < 3; channel++) {
                out[channel] = (unsigned char)llround(
                    out[channel] * (1.0 - alpha) + src[channel] * alpha
                );
            }
            if (memcmp(before, out, 4) != 0) {
                changed_pixels++;
                if (x < changed_min_x) changed_min_x = x;
                if (y < changed_min_y) changed_min_y = y;
                if (x > changed_max_x) changed_max_x = x;
                if (y > changed_max_y) changed_max_y = y;
            }
        }
    }

    if (!save_rgba(output_path, &final) || !load_rgba(output_path, &saved)) {
        fprintf(stderr, "Could not save or reload output PNG.\n");
        return 1;
    }

    printf("detected_cream_bounds=x%zu..%zu,y%zu..%zu\n", min_x, max_x, min_y, max_y);
    printf("composite_capsule_center=%.1f,%.1f\n", center_x, center_y);
    printf("composite_capsule_size=%.1fx%.1f\n", half_width * 2.0, half_height * 2.0);
    printf("changed_pixels=%zu\n", changed_pixels);
    printf("changed_bounds=x%zu..%zu,y%zu..%zu\n",
        changed_min_x, changed_max_x, changed_min_y, changed_max_y);
    printf("mismatched_pixels_above_footer=%zu\n",
        mismatch_count_above_row(&base, &saved, footer_top));
    printf("mismatched_pixels_outside_tag_capsule=%zu\n",
        mismatch_count_outside_capsule(
            &base, &saved, center_x, center_y, half_width, half_height
        ));

    free(base.pixels);
    free(edit.pixels);
    free(final.pixels);
    free(saved.pixels);
    return 0;
}
