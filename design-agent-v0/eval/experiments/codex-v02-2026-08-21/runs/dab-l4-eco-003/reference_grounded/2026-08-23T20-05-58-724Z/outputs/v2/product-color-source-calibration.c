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

typedef struct {
    double hue_degrees;
    double saturation;
    double value;
    size_t count;
} ColorStats;

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

static void rgb_to_hsv(
    unsigned char red, unsigned char green, unsigned char blue,
    double *hue, double *saturation, double *value
) {
    double r = red / 255.0;
    double g = green / 255.0;
    double b = blue / 255.0;
    double max_value = fmax(r, fmax(g, b));
    double min_value = fmin(r, fmin(g, b));
    double delta = max_value - min_value;

    *value = max_value;
    *saturation = max_value <= 0.0 ? 0.0 : delta / max_value;
    if (delta <= 0.000001) {
        *hue = 0.0;
    } else if (max_value == r) {
        *hue = 60.0 * fmod((g - b) / delta, 6.0);
    } else if (max_value == g) {
        *hue = 60.0 * (((b - r) / delta) + 2.0);
    } else {
        *hue = 60.0 * (((r - g) / delta) + 4.0);
    }
    if (*hue < 0.0) *hue += 360.0;
}

static void hsv_to_rgb(
    double hue, double saturation, double value,
    unsigned char *red, unsigned char *green, unsigned char *blue
) {
    while (hue < 0.0) hue += 360.0;
    while (hue >= 360.0) hue -= 360.0;
    saturation = clamp01(saturation);
    value = clamp01(value);

    double chroma = value * saturation;
    double x = chroma * (1.0 - fabs(fmod(hue / 60.0, 2.0) - 1.0));
    double m = value - chroma;
    double rp = 0.0, gp = 0.0, bp = 0.0;

    if (hue < 60.0) { rp = chroma; gp = x; }
    else if (hue < 120.0) { rp = x; gp = chroma; }
    else if (hue < 180.0) { gp = chroma; bp = x; }
    else if (hue < 240.0) { gp = x; bp = chroma; }
    else if (hue < 300.0) { rp = x; bp = chroma; }
    else { rp = chroma; bp = x; }

    *red = (unsigned char)llround((rp + m) * 255.0);
    *green = (unsigned char)llround((gp + m) * 255.0);
    *blue = (unsigned char)llround((bp + m) * 255.0);
}

static bool is_red_surface(unsigned char r, unsigned char g, unsigned char b) {
    return r > 55 && r > g + 22 && r > b + 20 && r - g > 26 && r - b > 30;
}

static double mask_strength(unsigned char r, unsigned char g, unsigned char b) {
    if (!is_red_surface(r, g, b)) return 0.0;
    double rg = ((double)r - (double)g - 22.0) / 22.0;
    double rb = ((double)r - (double)b - 20.0) / 22.0;
    return clamp01(fmin(rg, rb));
}

static ColorStats color_stats(
    const Raster *r, size_t x0, size_t y0, size_t x1, size_t y1
) {
    double sum_sin = 0.0;
    double sum_cos = 0.0;
    double sum_saturation = 0.0;
    double sum_value = 0.0;
    size_t count = 0;

    if (x1 > r->width) x1 = r->width;
    if (y1 > r->height) y1 = r->height;
    for (size_t y = y0; y < y1; y++) {
        const unsigned char *row = r->pixels + y * r->bytes_per_row;
        for (size_t x = x0; x < x1; x++) {
            const unsigned char *p = row + x * 4;
            if (!is_red_surface(p[0], p[1], p[2])) continue;
            double hue, saturation, value;
            rgb_to_hsv(p[0], p[1], p[2], &hue, &saturation, &value);
            double radians = hue * M_PI / 180.0;
            sum_sin += sin(radians) * saturation;
            sum_cos += cos(radians) * saturation;
            sum_saturation += saturation;
            sum_value += value;
            count++;
        }
    }

    ColorStats stats = {0};
    stats.count = count;
    if (count == 0) return stats;
    stats.hue_degrees = atan2(sum_sin, sum_cos) * 180.0 / M_PI;
    if (stats.hue_degrees < 0.0) stats.hue_degrees += 360.0;
    stats.saturation = sum_saturation / (double)count;
    stats.value = sum_value / (double)count;
    return stats;
}

static double shortest_hue_delta(double from, double to) {
    double delta = to - from;
    while (delta > 180.0) delta -= 360.0;
    while (delta < -180.0) delta += 360.0;
    return delta;
}

static size_t mismatched_pixels_outside_product_box(
    const Raster *base, const Raster *final,
    size_t x0, size_t y0, size_t x1, size_t y1
) {
    size_t mismatches = 0;
    for (size_t y = 0; y < base->height; y++) {
        const unsigned char *a = base->pixels + y * base->bytes_per_row;
        const unsigned char *b = final->pixels + y * final->bytes_per_row;
        for (size_t x = 0; x < base->width; x++) {
            if (x >= x0 && x < x1 && y >= y0 && y < y1) continue;
            if (memcmp(a + x * 4, b + x * 4, 4) != 0) mismatches++;
        }
    }
    return mismatches;
}

static size_t mismatched_pixels_outside_red_surface_mask(
    const Raster *base, const Raster *final,
    size_t x0, size_t y0, size_t x1, size_t y1
) {
    size_t mismatches = 0;
    for (size_t y = 0; y < base->height; y++) {
        const unsigned char *a = base->pixels + y * base->bytes_per_row;
        const unsigned char *b = final->pixels + y * final->bytes_per_row;
        for (size_t x = 0; x < base->width; x++) {
            bool allowed = x >= x0 && x < x1 && y >= y0 && y < y1 &&
                mask_strength(a[x * 4], a[x * 4 + 1], a[x * 4 + 2]) > 0.0;
            if (allowed) continue;
            if (memcmp(a + x * 4, b + x * 4, 4) != 0) mismatches++;
        }
    }
    return mismatches;
}

int main(int argc, char **argv) {
    const char *root = argc > 1 ? argv[1] : ".";
    char base_path[2048];
    char source_path[2048];
    char output_path[2048];
    snprintf(base_path, sizeof base_path,
        "%s/outputs/v1/taobao-first-screen-text-reduced-v1.png", root);
    snprintf(source_path, sizeof source_path,
        "%s/inputs/02-product_reference.png", root);
    snprintf(output_path, sizeof output_path,
        "%s/outputs/v2/taobao-first-screen-product-color-corrected-v2.png", root);

    Raster base = {0};
    Raster source = {0};
    Raster saved = {0};
    if (!load_rgba(base_path, &base) || !load_rgba(source_path, &source)) {
        fprintf(stderr, "Could not load input PNG files.\n");
        return 1;
    }

    const size_t bx0 = 260, by0 = 320, bx1 = 830, by1 = 740;
    const size_t sx0 = 215, sy0 = 300, sx1 = 810, sy1 = 730;
    ColorStats base_stats = color_stats(&base, bx0, by0, bx1, by1);
    ColorStats source_stats = color_stats(&source, sx0, sy0, sx1, sy1);
    if (base_stats.count == 0 || source_stats.count == 0) {
        fprintf(stderr, "Could not measure red product surfaces.\n");
        return 1;
    }

    double hue_delta = shortest_hue_delta(base_stats.hue_degrees, source_stats.hue_degrees);
    double saturation_scale = source_stats.saturation / base_stats.saturation;

    Raster final = base;
    final.pixels = malloc(base.bytes_per_row * base.height);
    if (!final.pixels) return 2;
    memcpy(final.pixels, base.pixels, base.bytes_per_row * base.height);

    size_t changed_pixels = 0;
    size_t min_x = base.width, min_y = base.height, max_x = 0, max_y = 0;
    for (size_t y = by0; y < by1; y++) {
        unsigned char *row = final.pixels + y * final.bytes_per_row;
        for (size_t x = bx0; x < bx1; x++) {
            unsigned char *p = row + x * 4;
            double strength = mask_strength(p[0], p[1], p[2]);
            if (strength <= 0.0) continue;

            double hue, saturation, value;
            rgb_to_hsv(p[0], p[1], p[2], &hue, &saturation, &value);
            unsigned char nr, ng, nb;
            hsv_to_rgb(
                hue + hue_delta,
                saturation * saturation_scale,
                value,
                &nr, &ng, &nb
            );

            unsigned char original_r = p[0];
            unsigned char original_g = p[1];
            unsigned char original_b = p[2];
            p[0] = (unsigned char)llround(original_r * (1.0 - strength) + nr * strength);
            p[1] = (unsigned char)llround(original_g * (1.0 - strength) + ng * strength);
            p[2] = (unsigned char)llround(original_b * (1.0 - strength) + nb * strength);

            if (p[0] != original_r || p[1] != original_g || p[2] != original_b) {
                changed_pixels++;
                if (x < min_x) min_x = x;
                if (y < min_y) min_y = y;
                if (x > max_x) max_x = x;
                if (y > max_y) max_y = y;
            }
        }
    }

    if (!save_rgba(output_path, &final) || !load_rgba(output_path, &saved)) {
        fprintf(stderr, "Could not save or reload output PNG.\n");
        return 1;
    }
    ColorStats final_stats = color_stats(&saved, bx0, by0, bx1, by1);

    printf("source_hue_degrees=%.3f\n", source_stats.hue_degrees);
    printf("base_hue_degrees=%.3f\n", base_stats.hue_degrees);
    printf("final_hue_degrees=%.3f\n", final_stats.hue_degrees);
    printf("source_saturation=%.5f\n", source_stats.saturation);
    printf("base_saturation=%.5f\n", base_stats.saturation);
    printf("final_saturation=%.5f\n", final_stats.saturation);
    printf("preserved_value_base=%.5f\n", base_stats.value);
    printf("preserved_value_final=%.5f\n", final_stats.value);
    printf("changed_product_surface_pixels=%zu\n", changed_pixels);
    printf("changed_bounds=x%zu..%zu,y%zu..%zu\n", min_x, max_x, min_y, max_y);
    printf("mismatched_pixels_outside_product_box=%zu\n",
        mismatched_pixels_outside_product_box(&base, &saved, bx0, by0, bx1, by1));
    printf("mismatched_pixels_outside_red_surface_mask=%zu\n",
        mismatched_pixels_outside_red_surface_mask(&base, &saved, bx0, by0, bx1, by1));
    printf("final_hue_error_degrees=%.3f\n",
        fabs(shortest_hue_delta(final_stats.hue_degrees, source_stats.hue_degrees)));
    printf("final_saturation_error=%.5f\n",
        fabs(final_stats.saturation - source_stats.saturation));

    free(base.pixels);
    free(source.pixels);
    free(final.pixels);
    free(saved.pixels);
    return 0;
}
