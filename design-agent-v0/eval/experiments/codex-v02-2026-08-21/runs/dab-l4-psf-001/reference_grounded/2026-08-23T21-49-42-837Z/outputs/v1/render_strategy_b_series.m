#import <AppKit/AppKit.h>

static const CGFloat BW = 2400.0;
static const CGFloat BH = 1350.0;
static NSImage *ApprovedBase;
static NSColor *Charcoal, *Paper, *Card, *Rule, *Muted, *Sage, *Mist, *Terracotta;

static NSRect TopRect(CGFloat x, CGFloat top, CGFloat width, CGFloat height, CGFloat canvasHeight) {
    return NSMakeRect(x, canvasHeight - top - height, width, height);
}

static NSFont *Font(CGFloat size, NSFontWeight weight) {
    return [NSFont systemFontOfSize:size weight:weight];
}

static NSFont *SerifFont(CGFloat size) {
    return [NSFont fontWithName:@"Songti SC" size:size] ?: [NSFont systemFontOfSize:size];
}

static void DrawText(NSString *text, NSRect rect, CGFloat size, NSFontWeight weight,
                     NSColor *color, NSTextAlignment alignment, CGFloat kern, BOOL serif) {
    NSMutableParagraphStyle *paragraph = [[NSMutableParagraphStyle alloc] init];
    paragraph.alignment = alignment;
    paragraph.lineBreakMode = NSLineBreakByTruncatingTail;
    NSDictionary *attrs = @{
        NSFontAttributeName: serif ? SerifFont(size) : Font(size, weight),
        NSForegroundColorAttributeName: color ?: Charcoal,
        NSParagraphStyleAttributeName: paragraph,
        NSKernAttributeName: @(kern)
    };
    [text drawInRect:rect withAttributes:attrs];
}

static void DrawSimpleText(NSString *text, NSRect rect, CGFloat size, NSFontWeight weight,
                           NSColor *color, NSTextAlignment alignment) {
    DrawText(text, rect, size, weight, color, alignment, 0, NO);
}

static void RoundedCard(NSRect rect, CGFloat radius) {
    [NSGraphicsContext saveGraphicsState];
    NSShadow *shadow = [[NSShadow alloc] init];
    shadow.shadowColor = [NSColor colorWithWhite:0 alpha:0.08];
    shadow.shadowBlurRadius = 18;
    shadow.shadowOffset = NSMakeSize(0, -5);
    [shadow set];
    [Card setFill];
    [[NSBezierPath bezierPathWithRoundedRect:rect xRadius:radius yRadius:radius] fill];
    [NSGraphicsContext restoreGraphicsState];
}

static CGPathRef CreateBodyClipPath(void) {
    CGMutablePathRef path = CGPathCreateMutable();
    CGPathMoveToPoint(path, NULL, 370, 770);
    CGPathAddLineToPoint(path, NULL, 650, 770);
    CGPathAddLineToPoint(path, NULL, 650, 235);
    CGPathAddCurveToPoint(path, NULL, 650, 205, 642, 182, 620, 170);
    CGPathAddCurveToPoint(path, NULL, 585, 156, 545, 150, 510, 151);
    CGPathAddCurveToPoint(path, NULL, 475, 150, 435, 156, 400, 170);
    CGPathAddCurveToPoint(path, NULL, 378, 184, 370, 205, 370, 235);
    CGPathCloseSubpath(path);
    return path;
}

static void DrawLeafMark(CGContextRef context, CGPoint center, CGFloat radius,
                         NSColor *fill, NSColor *vein, CGFloat lineWidth) {
    CGContextSaveGState(context);
    CGContextSetBlendMode(context, kCGBlendModeNormal);
    CGRect oval = CGRectMake(center.x - radius, center.y - radius, radius * 2, radius * 2);
    CGContextAddEllipseInRect(context, oval);
    CGContextClip(context);
    CGContextSetFillColorWithColor(context, fill.CGColor);
    CGContextFillRect(context, oval);
    CGContextSetStrokeColorWithColor(context, vein.CGColor);
    CGContextSetLineWidth(context, lineWidth);
    CGContextSetLineCap(context, kCGLineCapRound);
    CGContextMoveToPoint(context, center.x, center.y - radius * 0.92);
    CGContextAddCurveToPoint(context, center.x - radius * 0.02, center.y - radius * 0.35,
                             center.x + radius * 0.04, center.y + radius * 0.40,
                             center.x, center.y + radius * 0.92);
    CGContextStrokePath(context);
    CGFloat levels[] = {-0.55, -0.18, 0.18, 0.52};
    for (int i = 0; i < 4; i++) {
        CGFloat level = levels[i];
        CGFloat y = center.y + radius * level;
        CGFloat spread = radius * (0.70 - fabs(level) * 0.35);
        CGContextMoveToPoint(context, center.x, y);
        CGContextAddCurveToPoint(context, center.x - radius * 0.22, y + radius * 0.02,
                                 center.x - spread * 0.72, y + radius * 0.18,
                                 center.x - spread, y + radius * 0.28);
        CGContextStrokePath(context);
        CGContextMoveToPoint(context, center.x, y);
        CGContextAddCurveToPoint(context, center.x + radius * 0.22, y + radius * 0.02,
                                 center.x + spread * 0.72, y + radius * 0.18,
                                 center.x + spread, y + radius * 0.28);
        CGContextStrokePath(context);
    }
    CGContextRestoreGState(context);
}

static void DrawHierarchy(NSColor *flavorColor) {
    DrawText(@"MORI", TopRect(365, 332, 290, 62, 1024), 43, NSFontWeightSemibold,
             Charcoal, NSTextAlignmentCenter, 11, NO);
    DrawText(@"茉莉", TopRect(372, 492, 276, 64, 1024), 42, NSFontWeightRegular,
             flavorColor ?: Charcoal, NSTextAlignmentCenter, 0, YES);
    DrawText(@"净含量 XXX mL", TopRect(382, 695, 256, 26, 1024), 17, NSFontWeightMedium,
             [Charcoal colorWithAlphaComponent:0.82], NSTextAlignmentCenter, 0.5, NO);
    DrawText(@"基础卖点", TopRect(382, 726, 256, 24, 1024), 16, NSFontWeightRegular,
             [Charcoal colorWithAlphaComponent:0.62], NSTextAlignmentCenter, 1.2, NO);
}

static NSImage *MakeVariant(NSInteger kind, NSColor *accent) {
    NSSize size = NSMakeSize(1024, 1024);
    NSImage *image = [[NSImage alloc] initWithSize:size];
    [image lockFocus];
    [[NSColor whiteColor] setFill];
    NSRectFill(NSMakeRect(0, 0, 1024, 1024));
    [ApprovedBase drawInRect:NSMakeRect(0, 0, 1024, 1024)
                    fromRect:NSMakeRect(0, 0, ApprovedBase.size.width, ApprovedBase.size.height)
                   operation:NSCompositingOperationSourceOver fraction:1.0];
    CGContextRef context = NSGraphicsContext.currentContext.CGContext;
    CGContextSaveGState(context);
    CGPathRef clip = CreateBodyClipPath();
    CGContextAddPath(context, clip);
    CGContextClip(context);
    CGPathRelease(clip);
    CGContextSetBlendMode(context, kCGBlendModeMultiply);
    CGContextSetFillColorWithColor(context, [accent colorWithAlphaComponent:0.78].CGColor);
    CGContextSetStrokeColorWithColor(context, accent.CGColor);

    switch (kind) {
        case 1:
            CGContextFillRect(context, CGRectMake(370, 748, 280, 20)); break;
        case 2:
            CGContextFillRect(context, CGRectMake(370, 575, 280, 195)); break;
        case 3:
            CGContextFillRect(context, CGRectMake(370, 425, 280, 126)); break;
        case 4:
            CGContextFillRect(context, CGRectMake(370, 150, 280, 240)); break;
        case 5:
            DrawLeafMark(context, CGPointMake(533, 470), 150,
                         [accent colorWithAlphaComponent:0.18], [[NSColor whiteColor] colorWithAlphaComponent:0.72], 15); break;
        case 6:
            DrawLeafMark(context, CGPointMake(510, 470), 45, accent, NSColor.whiteColor, 5); break;
        case 7:
            for (int row = 0; row < 3; row++) {
                for (int col = 0; col < 4; col++) {
                    CGPoint c = CGPointMake(402 + col * 72, 235 + row * 66);
                    DrawLeafMark(context, c, 26, [accent colorWithAlphaComponent:(row % 2 == 0 ? 0.64 : 0.38)], NSColor.whiteColor, 3);
                }
            }
            break;
        case 8:
            CGContextSetLineWidth(context, 9);
            for (int i = 0; i < 2; i++) {
                CGFloat x = i == 0 ? 414 : 606;
                CGContextMoveToPoint(context, x, 205);
                CGContextAddLineToPoint(context, x, 720);
                CGContextStrokePath(context);
            }
            break;
        case 9:
            CGContextFillEllipseInRect(context, CGRectMake(500, 420, 20, 20)); break;
        case 10:
            CGContextFillRect(context, CGRectMake(615, 205, 35, 565)); break;
        case 11:
            DrawLeafMark(context, CGPointMake(555, 440), 165,
                         [accent colorWithAlphaComponent:0.18], [[NSColor whiteColor] colorWithAlphaComponent:0.75], 16);
            DrawLeafMark(context, CGPointMake(510, 455), 35, accent, NSColor.whiteColor, 4);
            break;
        case 12:
            CGContextSetLineWidth(context, 5);
            for (int i = 0; i < 2; i++) {
                CGFloat x = i == 0 ? 392 : 628;
                CGContextMoveToPoint(context, x, 225);
                CGContextAddLineToPoint(context, x, 735);
                CGContextStrokePath(context);
            }
            CGContextFillEllipseInRect(context, CGRectMake(500, 420, 20, 20));
            break;
        default: break;
    }
    CGContextRestoreGState(context);
    DrawHierarchy((kind == 9 || kind == 12) ? accent : nil);
    [image unlockFocus];
    return image;
}

static NSRect SourceCrop(void) { return NSMakeRect(325, 114, 370, 780); }

static void DrawPack(NSImage *image, NSRect target) {
    [image drawInRect:target fromRect:SourceCrop() operation:NSCompositingOperationSourceOver fraction:1.0];
}

static NSBitmapImageRep *BeginBitmap(void) {
    NSBitmapImageRep *rep = [[NSBitmapImageRep alloc]
        initWithBitmapDataPlanes:NULL pixelsWide:(NSInteger)BW pixelsHigh:(NSInteger)BH
        bitsPerSample:8 samplesPerPixel:4 hasAlpha:YES isPlanar:NO
        colorSpaceName:NSDeviceRGBColorSpace bytesPerRow:0 bitsPerPixel:0];
    rep.size = NSMakeSize(BW, BH);
    [NSGraphicsContext saveGraphicsState];
    [NSGraphicsContext setCurrentContext:[NSGraphicsContext graphicsContextWithBitmapImageRep:rep]];
    return rep;
}

static void SaveBitmap(NSBitmapImageRep *rep, NSString *name, NSURL *workspace) {
    [NSGraphicsContext.currentContext flushGraphics];
    [NSGraphicsContext restoreGraphicsState];
    NSData *data = [rep representationUsingType:NSBitmapImageFileTypePNG properties:@{}];
    NSURL *out = [[workspace URLByAppendingPathComponent:@"outputs/v1"] URLByAppendingPathComponent:name];
    NSError *error = nil;
    if (![data writeToURL:out options:NSDataWritingAtomic error:&error]) {
        NSLog(@"Write failed: %@", error);
        exit(2);
    }
}

static void FillBackground(void) {
    [Paper setFill];
    NSRectFill(NSMakeRect(0, 0, BW, BH));
}

static NSArray<NSDictionary *> *FlavorData(void) {
    return @[
        @{@"name": @"茉莉", @"hex": @"#E3DFC6", @"color": [NSColor colorWithCalibratedRed:0.89 green:0.87 blue:0.78 alpha:1], @"border": Sage},
        @{@"name": @"乌龙", @"hex": @"#6F7D50", @"color": [NSColor colorWithCalibratedRed:0.44 green:0.49 blue:0.31 alpha:1]},
        @{@"name": @"白桃", @"hex": @"#D98F79", @"color": [NSColor colorWithCalibratedRed:0.85 green:0.56 blue:0.47 alpha:1]},
        @{@"name": @"桂花", @"hex": @"#C79543", @"color": [NSColor colorWithCalibratedRed:0.78 green:0.58 blue:0.26 alpha:1]},
        @{@"name": @"青柠", @"hex": @"#A1B36B", @"color": [NSColor colorWithCalibratedRed:0.631 green:0.702 blue:0.420 alpha:1]}
    ];
}

static void DrawSeriesHierarchy(NSString *flavorName) {
    DrawText(@"MORI", TopRect(365, 332, 290, 62, 1024), 43, NSFontWeightSemibold,
             Charcoal, NSTextAlignmentCenter, 11, NO);
    DrawText(flavorName, TopRect(372, 492, 276, 64, 1024), 42, NSFontWeightRegular,
             Charcoal, NSTextAlignmentCenter, 0, YES);
    DrawText(@"净含量 XXX mL", TopRect(382, 695, 256, 26, 1024), 17, NSFontWeightMedium,
             [Charcoal colorWithAlphaComponent:0.82], NSTextAlignmentCenter, 0.5, NO);
    DrawText(@"基础卖点", TopRect(382, 726, 256, 24, 1024), 16, NSFontWeightRegular,
             [Charcoal colorWithAlphaComponent:0.62], NSTextAlignmentCenter, 1.2, NO);
}

static NSImage *MakeSeriesVariant(NSDictionary *flavor) {
    NSColor *accent = flavor[@"color"];
    NSColor *border = flavor[@"border"];
    NSString *flavorName = flavor[@"name"];
    NSSize size = NSMakeSize(1024, 1024);
    NSImage *image = [[NSImage alloc] initWithSize:size];
    [image lockFocus];
    [[NSColor whiteColor] setFill];
    NSRectFill(NSMakeRect(0, 0, 1024, 1024));
    [ApprovedBase drawInRect:NSMakeRect(0, 0, 1024, 1024)
                    fromRect:NSMakeRect(0, 0, ApprovedBase.size.width, ApprovedBase.size.height)
                   operation:NSCompositingOperationSourceOver fraction:1.0];
    CGContextRef context = NSGraphicsContext.currentContext.CGContext;
    CGContextSaveGState(context);
    CGPathRef clip = CreateBodyClipPath();
    CGContextAddPath(context, clip);
    CGContextClip(context);
    CGPathRelease(clip);
    NSColor *largeVein = border ? [border colorWithAlphaComponent:0.72] : [[NSColor whiteColor] colorWithAlphaComponent:0.78];
    NSColor *smallVein = border ?: NSColor.whiteColor;
    DrawLeafMark(context, CGPointMake(555, 440), 165,
                 [accent colorWithAlphaComponent:(border ? 0.36 : 0.22)], largeVein, 16);
    DrawLeafMark(context, CGPointMake(510, 455), 35, accent, smallVein, 4);
    if (border) {
        CGContextSetStrokeColorWithColor(context, border.CGColor);
        CGContextSetLineWidth(context, 4);
        CGContextStrokeEllipseInRect(context, CGRectMake(475, 420, 70, 70));
    }
    CGContextRestoreGState(context);
    DrawSeriesHierarchy(flavorName);
    [image unlockFocus];
    return image;
}

static void RenderHypothesisBoard(NSURL *workspace) {
    NSArray *items = @[
        @{@"id":@"01", @"name":@"顶部领环", @"kind":@1, @"accent":Sage},
        @{@"id":@"02", @"name":@"上段色罩", @"kind":@2, @"accent":Sage},
        @{@"id":@"03", @"name":@"中腰色带", @"kind":@3, @"accent":Sage},
        @{@"id":@"04", @"name":@"底部色舱", @"kind":@4, @"accent":Sage},
        @{@"id":@"05", @"name":@"大叶水印", @"kind":@5, @"accent":Mist},
        @{@"id":@"06", @"name":@"叶形徽章", @"kind":@6, @"accent":Mist},
        @{@"id":@"07", @"name":@"底部纹样", @"kind":@7, @"accent":Mist},
        @{@"id":@"08", @"name":@"双竖色线", @"kind":@8, @"accent":Terracotta},
        @{@"id":@"09", @"name":@"字色 + 色点", @"kind":@9, @"accent":Terracotta},
        @{@"id":@"10", @"name":@"侧边色签", @"kind":@10, @"accent":Terracotta}
    ];
    NSBitmapImageRep *rep = BeginBitmap();
    FillBackground();
    DrawSimpleText(@"MORI · 色彩编码假设 v0", TopRect(90, 52, 1150, 58, BH), 46, NSFontWeightSemibold, Charcoal, NSTextAlignmentLeft);
    DrawSimpleText(@"仅改变印刷色码｜批准杯体、Logo、口味名、净含量与基础卖点层级锁定", TopRect(90, 112, 1500, 38, BH), 23, NSFontWeightRegular, Muted, NSTextAlignmentLeft);
    DrawSimpleText(@"10 个低成本假设 · 单专色 + 黑", TopRect(1740, 70, 570, 38, BH), 22, NSFontWeightMedium, Sage, NSTextAlignmentRight);

    CGFloat margin = 90, gap = 24;
    CGFloat cardW = (BW - margin * 2 - gap * 4) / 5;
    CGFloat cardH = 515;
    CGFloat rowTops[] = {185, 725};
    for (NSInteger index = 0; index < items.count; index++) {
        NSDictionary *item = items[index];
        NSInteger row = index / 5, col = index % 5;
        CGFloat x = margin + col * (cardW + gap), top = rowTops[row];
        RoundedCard(TopRect(x, top, cardW, cardH, BH), 22);
        NSString *cluster = index < 4 ? @"A · 色域位置" : (index < 7 ? @"B · 叶形资产" : @"C · 线性色码");
        NSColor *clusterColor = index < 4 ? Sage : (index < 7 ? Mist : Terracotta);
        [clusterColor setFill];
        [[NSBezierPath bezierPathWithRoundedRect:TopRect(x+20, top+18, 126, 28, BH) xRadius:14 yRadius:14] fill];
        DrawSimpleText(cluster, TopRect(x+21, top+21, 124, 23, BH), 13, NSFontWeightSemibold, NSColor.whiteColor, NSTextAlignmentCenter);
        DrawSimpleText(item[@"id"], TopRect(x+cardW-72, top+15, 48, 36, BH), 26, NSFontWeightSemibold, Charcoal, NSTextAlignmentRight);
        NSImage *variant = MakeVariant([item[@"kind"] integerValue], item[@"accent"]);
        CGFloat packH = 350, packW = packH * SourceCrop().size.width / SourceCrop().size.height;
        DrawPack(variant, TopRect(x+(cardW-packW)/2, top+70, packW, packH, BH));
        DrawSimpleText(item[@"name"], TopRect(x+22, top+431, cardW-44, 34, BH), 24, NSFontWeightSemibold, Charcoal, NSTextAlignmentCenter);
        DrawSimpleText(@"1 专色 · 结构零改动", TopRect(x+22, top+469, cardW-44, 24, BH), 15, NSFontWeightRegular, Muted, NSTextAlignmentCenter);
    }
    DrawSimpleText(@"聚类依据：色彩占比、品牌资产参与度、缩略图/货架识别距离", TopRect(90, 1270, 1400, 30, BH), 18, NSFontWeightRegular, Muted, NSTextAlignmentLeft);
    DrawSimpleText(@"探索图，不代表最终五款展开", TopRect(1780, 1270, 530, 30, BH), 18, NSFontWeightRegular, Muted, NSTextAlignmentRight);
    SaveBitmap(rep, @"03_locked_color_encoding_hypotheses.png", workspace);
}

static void DrawFlavorStrip(CGFloat x, CGFloat top, CGFloat cardW) {
    NSArray *flavors = FlavorData();
    CGFloat gap = 15;
    CGFloat chipW = (cardW - 60 - gap * 4) / 5;
    for (NSInteger i = 0; i < flavors.count; i++) {
        NSDictionary *flavor = flavors[i];
        CGFloat chipX = x + 30 + i * (chipW + gap);
        [flavor[@"color"] setFill];
        NSBezierPath *circle = [NSBezierPath bezierPathWithOvalInRect:TopRect(chipX+(chipW-42)/2, top+705, 42, 42, BH)];
        [circle fill];
        if (flavor[@"border"]) {
            [flavor[@"border"] setStroke];
            circle.lineWidth = 3;
            [circle stroke];
        }
        DrawSimpleText(flavor[@"name"], TopRect(chipX, top+755, chipW, 26, BH), 17, NSFontWeightMedium, Charcoal, NSTextAlignmentCenter);
        DrawSimpleText(flavor[@"hex"], TopRect(chipX, top+784, chipW, 20, BH), 12, NSFontWeightRegular, Muted, NSTextAlignmentCenter);
    }
}

static void RenderStrategyBoard(NSURL *workspace) {
    NSArray *strategies = @[
        @{@"letter":@"A", @"name":@"色域舱", @"subtitle":@"大色块 · 远距优先", @"kind":@4, @"accent":Sage,
          @"metrics":@[@[@"线上缩略图",@"强"],@[@"线下货架",@"最强"],@[@"印刷",@"1 专色 + 黑 / 大覆盖"]], @"caution":@"浅色茉莉款需保留绿色描边"},
        @{@"letter":@"B", @"name":@"叶印章", @"subtitle":@"品牌资产 · 平衡型", @"kind":@11, @"accent":Mist,
          @"metrics":@[@[@"线上缩略图",@"中强"],@[@"线下货架",@"强"],@[@"印刷",@"1 专色 + 黑 / 中覆盖"]], @"caution":@"水印与信息区保持对比安全距"},
        @{@"letter":@"C", @"name":@"微型色码", @"subtitle":@"最低墨量 · 克制型", @"kind":@12, @"accent":Terracotta,
          @"metrics":@[@[@"线上缩略图",@"中"],@[@"线下货架",@"中"],@[@"印刷",@"1 专色 + 黑 / 最低覆盖"]], @"caution":@"远距区分弱于 A / B"}
    ];
    NSBitmapImageRep *rep = BeginBitmap();
    FillBackground();
    DrawSimpleText(@"3 个系列策略 · 待选择", TopRect(90, 52, 1000, 58, BH), 46, NSFontWeightSemibold, Charcoal, NSTextAlignmentLeft);
    DrawSimpleText(@"同一五味色谱，不同编码机制；选择后才展开完整五款", TopRect(90, 112, 1450, 38, BH), 23, NSFontWeightRegular, Muted, NSTextAlignmentLeft);
    DrawSimpleText(@"决策门：A / B / C", TopRect(1760, 68, 550, 38, BH), 24, NSFontWeightSemibold, Terracotta, NSTextAlignmentRight);

    CGFloat margin = 90, gap = 32;
    CGFloat cardW = (BW - margin * 2 - gap * 2) / 3;
    CGFloat cardTop = 185, cardH = 1070;
    for (NSInteger index = 0; index < strategies.count; index++) {
        NSDictionary *strategy = strategies[index];
        CGFloat x = margin + index * (cardW + gap);
        RoundedCard(TopRect(x, cardTop, cardW, cardH, BH), 28);
        [strategy[@"accent"] setFill];
        [[NSBezierPath bezierPathWithRoundedRect:TopRect(x+28, cardTop+28, 62, 62, BH) xRadius:31 yRadius:31] fill];
        DrawSimpleText(strategy[@"letter"], TopRect(x+28, cardTop+37, 62, 44, BH), 30, NSFontWeightBold, NSColor.whiteColor, NSTextAlignmentCenter);
        DrawSimpleText(strategy[@"name"], TopRect(x+112, cardTop+27, cardW-142, 40, BH), 32, NSFontWeightSemibold, Charcoal, NSTextAlignmentLeft);
        DrawSimpleText(strategy[@"subtitle"], TopRect(x+112, cardTop+70, cardW-142, 30, BH), 19, NSFontWeightRegular, Muted, NSTextAlignmentLeft);
        NSImage *variant = MakeVariant([strategy[@"kind"] integerValue], strategy[@"accent"]);
        CGFloat packH = 535, packW = packH * SourceCrop().size.width / SourceCrop().size.height;
        DrawPack(variant, TopRect(x+(cardW-packW)/2, cardTop+118, packW, packH, BH));
        DrawSimpleText(@"五味色谱测试", TopRect(x+30, cardTop+660, cardW-60, 26, BH), 18, NSFontWeightSemibold, Muted, NSTextAlignmentLeft);
        DrawFlavorStrip(x, cardTop, cardW);

        [Rule setStroke];
        NSBezierPath *divider = [NSBezierPath bezierPath];
        [divider moveToPoint:NSMakePoint(x+30, BH-(cardTop+830))];
        [divider lineToPoint:NSMakePoint(x+cardW-30, BH-(cardTop+830))];
        divider.lineWidth = 1;
        [divider stroke];
        NSArray *metrics = strategy[@"metrics"];
        for (NSInteger row = 0; row < metrics.count; row++) {
            NSArray *metric = metrics[row];
            CGFloat y = cardTop + 852 + row * 42;
            DrawSimpleText(metric[0], TopRect(x+34, y, 175, 28, BH), 17, NSFontWeightRegular, Muted, NSTextAlignmentLeft);
            DrawSimpleText(metric[1], TopRect(x+215, y, cardW-250, 28, BH), 17, NSFontWeightSemibold, Charcoal, NSTextAlignmentRight);
        }
        NSString *caution = [@"注意：" stringByAppendingString:strategy[@"caution"]];
        DrawSimpleText(caution, TopRect(x+34, cardTop+992, cardW-68, 30, BH), 15, NSFontWeightRegular, strategy[@"accent"], NSTextAlignmentLeft);
    }
    DrawSimpleText(@"锁定：容器比例 · 黑色杯盖 · MORI Logo · 信息层级 · 净含量与基础卖点位置", TopRect(90, 1282, 1700, 28, BH), 17, NSFontWeightRegular, Muted, NSTextAlignmentLeft);
    DrawSimpleText(@"请选择 1 个策略后进入五 SKU 完整展开", TopRect(1740, 1282, 570, 28, BH), 17, NSFontWeightSemibold, Terracotta, NSTextAlignmentRight);
    SaveBitmap(rep, @"04_locked_three_strategy_choice_board.png", workspace);
}

static void RenderFullSeriesBoard(NSURL *workspace) {
    NSArray *flavors = FlavorData();
    NSBitmapImageRep *rep = BeginBitmap();
    FillBackground();
    DrawSimpleText(@"MORI · 叶印章系列 v1", TopRect(90, 48, 1100, 60, BH), 46, NSFontWeightSemibold, Charcoal, NSTextAlignmentLeft);
    DrawSimpleText(@"策略 B 已确认｜恰好五款｜仅青柠由冷雾青绿调整为同明度偏黄绿", TopRect(90, 110, 1650, 38, BH), 23, NSFontWeightRegular, Muted, NSTextAlignmentLeft);
    DrawSimpleText(@"结构 / Logo / 信息层级锁定", TopRect(1720, 68, 590, 36, BH), 21, NSFontWeightSemibold, Sage, NSTextAlignmentRight);

    CGFloat margin = 90, gap = 24;
    CGFloat cardW = (BW - margin * 2 - gap * 4) / 5;
    CGFloat cardTop = 180, cardH = 1060;
    for (NSInteger index = 0; index < flavors.count; index++) {
        NSDictionary *flavor = flavors[index];
        CGFloat x = margin + index * (cardW + gap);
        NSColor *accent = flavor[@"border"] ?: flavor[@"color"];
        RoundedCard(TopRect(x, cardTop, cardW, cardH, BH), 24);
        [accent setFill];
        [[NSBezierPath bezierPathWithRoundedRect:TopRect(x, cardTop, cardW, 10, BH) xRadius:5 yRadius:5] fill];
        NSString *indexText = [NSString stringWithFormat:@"%02ld", (long)(index + 1)];
        DrawSimpleText(indexText, TopRect(x+24, cardTop+28, 58, 34, BH), 24, NSFontWeightSemibold, accent, NSTextAlignmentLeft);
        DrawSimpleText(flavor[@"name"], TopRect(x+82, cardTop+25, cardW-106, 40, BH), 30, NSFontWeightSemibold, Charcoal, NSTextAlignmentLeft);
        DrawSimpleText(flavor[@"hex"], TopRect(x+82, cardTop+68, cardW-106, 24, BH), 15, NSFontWeightRegular, Muted, NSTextAlignmentLeft);

        NSImage *variant = MakeSeriesVariant(flavor);
        CGFloat packH = 640, packW = packH * SourceCrop().size.width / SourceCrop().size.height;
        DrawPack(variant, TopRect(x+(cardW-packW)/2, cardTop+112, packW, packH, BH));

        [flavor[@"color"] setFill];
        NSBezierPath *chip = [NSBezierPath bezierPathWithOvalInRect:TopRect(x+36, cardTop+790, 46, 46, BH)];
        [chip fill];
        if (flavor[@"border"]) {
            [flavor[@"border"] setStroke];
            chip.lineWidth = 3;
            [chip stroke];
        }
        DrawSimpleText(@"B · 叶印章", TopRect(x+98, cardTop+790, cardW-130, 30, BH), 19, NSFontWeightSemibold, Charcoal, NSTextAlignmentLeft);
        DrawSimpleText(@"大叶水印 + 小叶徽章", TopRect(x+98, cardTop+825, cardW-130, 26, BH), 15, NSFontWeightRegular, Muted, NSTextAlignmentLeft);

        [Rule setStroke];
        NSBezierPath *divider = [NSBezierPath bezierPath];
        [divider moveToPoint:NSMakePoint(x+28, BH-(cardTop+878))];
        [divider lineToPoint:NSMakePoint(x+cardW-28, BH-(cardTop+878))];
        divider.lineWidth = 1;
        [divider stroke];
        DrawSimpleText(@"印刷", TopRect(x+30, cardTop+900, 80, 25, BH), 15, NSFontWeightRegular, Muted, NSTextAlignmentLeft);
        DrawSimpleText(@"1 专色 + 黑", TopRect(x+112, cardTop+900, cardW-142, 25, BH), 15, NSFontWeightSemibold, Charcoal, NSTextAlignmentRight);
        NSString *status = index == 4 ? @"本轮调整 · 同明度偏黄绿" : @"沿用 v0 已提案色值";
        DrawSimpleText(status, TopRect(x+30, cardTop+950, cardW-60, 28, BH), 15, index == 4 ? NSFontWeightSemibold : NSFontWeightRegular,
                       index == 4 ? accent : Muted, NSTextAlignmentCenter);
    }
    DrawSimpleText(@"统一位置：MORI Logo → 口味名 → 净含量 → 基础卖点", TopRect(90, 1278, 1350, 28, BH), 17, NSFontWeightRegular, Muted, NSTextAlignmentLeft);
    DrawSimpleText(@"最终 SKU 数：5", TopRect(1870, 1278, 440, 28, BH), 17, NSFontWeightSemibold, Sage, NSTextAlignmentRight);
    SaveBitmap(rep, @"01_strategy_b_full_five_sku_series.png", workspace);
}

static void RenderShelfThumbnailBoard(NSURL *workspace) {
    NSArray *flavors = FlavorData();
    NSBitmapImageRep *rep = BeginBitmap();
    FillBackground();
    DrawSimpleText(@"策略 B · 货架与缩略图检查", TopRect(90, 48, 1250, 60, BH), 46, NSFontWeightSemibold, Charcoal, NSTextAlignmentLeft);
    DrawSimpleText(@"同一杯体、同一层级、同一明度秩序；青柠为低饱和偏黄绿", TopRect(90, 110, 1600, 38, BH), 23, NSFontWeightRegular, Muted, NSTextAlignmentLeft);

    RoundedCard(TopRect(90, 170, 2220, 690, BH), 28);
    DrawSimpleText(@"线下货架 · 同距同尺度", TopRect(125, 195, 650, 32, BH), 21, NSFontWeightSemibold, Muted, NSTextAlignmentLeft);
    CGFloat shelfPackH = 545, shelfPackW = shelfPackH * SourceCrop().size.width / SourceCrop().size.height;
    CGFloat shelfGap = 92;
    CGFloat shelfTotal = shelfPackW * 5 + shelfGap * 4;
    CGFloat shelfX = (BW - shelfTotal) / 2;
    for (NSInteger i = 0; i < flavors.count; i++) {
        NSDictionary *flavor = flavors[i];
        NSImage *variant = MakeSeriesVariant(flavor);
        CGFloat x = shelfX + i * (shelfPackW + shelfGap);
        DrawPack(variant, TopRect(x, 245, shelfPackW, shelfPackH, BH));
        DrawSimpleText(flavor[@"name"], TopRect(x, 785, shelfPackW, 30, BH), 19, NSFontWeightSemibold, Charcoal, NSTextAlignmentCenter);
    }
    [Rule setStroke];
    NSBezierPath *shelf = [NSBezierPath bezierPath];
    [shelf moveToPoint:NSMakePoint(145, BH-780)];
    [shelf lineToPoint:NSMakePoint(BW-145, BH-780)];
    shelf.lineWidth = 3;
    [shelf stroke];

    RoundedCard(TopRect(90, 890, 2220, 340, BH), 28);
    DrawSimpleText(@"线上缩略图 · 120 px 代理", TopRect(125, 915, 650, 32, BH), 21, NSFontWeightSemibold, Muted, NSTextAlignmentLeft);
    CGFloat thumbPackH = 190, thumbPackW = thumbPackH * SourceCrop().size.width / SourceCrop().size.height;
    CGFloat thumbCellW = 360, thumbGap = 45;
    CGFloat thumbTotal = thumbCellW * 5 + thumbGap * 4;
    CGFloat thumbX = (BW - thumbTotal) / 2;
    for (NSInteger i = 0; i < flavors.count; i++) {
        NSDictionary *flavor = flavors[i];
        NSImage *variant = MakeSeriesVariant(flavor);
        CGFloat cellX = thumbX + i * (thumbCellW + thumbGap);
        CGFloat packX = cellX + 24;
        DrawPack(variant, TopRect(packX, 970, thumbPackW, thumbPackH, BH));
        [flavor[@"color"] setFill];
        NSBezierPath *chip = [NSBezierPath bezierPathWithOvalInRect:TopRect(cellX+150, 1020, 48, 48, BH)];
        [chip fill];
        if (flavor[@"border"]) {
            [flavor[@"border"] setStroke]; chip.lineWidth = 3; [chip stroke];
        }
        DrawSimpleText(flavor[@"name"], TopRect(cellX+215, 1016, 120, 30, BH), 21, NSFontWeightSemibold, Charcoal, NSTextAlignmentLeft);
        DrawSimpleText(flavor[@"hex"], TopRect(cellX+215, 1052, 120, 22, BH), 14, NSFontWeightRegular, Muted, NSTextAlignmentLeft);
    }
    DrawSimpleText(@"检查结果：五款均可区分；青柠不使用荧光绿", TopRect(90, 1278, 1250, 28, BH), 17, NSFontWeightSemibold, Sage, NSTextAlignmentLeft);
    DrawSimpleText(@"结构与信息层级未变", TopRect(1750, 1278, 560, 28, BH), 17, NSFontWeightRegular, Muted, NSTextAlignmentRight);
    SaveBitmap(rep, @"02_strategy_b_shelf_thumbnail_check.png", workspace);
}

int main(void) {
    @autoreleasepool {
        NSURL *workspace = [NSURL fileURLWithPath:NSFileManager.defaultManager.currentDirectoryPath];
        NSURL *baseURL = [workspace URLByAppendingPathComponent:@"inputs/02-approved_base_packaging.png"];
        ApprovedBase = [[NSImage alloc] initWithContentsOfURL:baseURL];
        if (!ApprovedBase) { NSLog(@"Unable to load approved base"); return 1; }
        Charcoal = [NSColor colorWithCalibratedRed:0.17 green:0.18 blue:0.17 alpha:1];
        Paper = [NSColor colorWithCalibratedRed:0.965 green:0.953 blue:0.914 alpha:1];
        Card = [NSColor colorWithCalibratedRed:0.992 green:0.989 blue:0.974 alpha:1];
        Rule = [NSColor colorWithCalibratedRed:0.83 green:0.82 blue:0.78 alpha:1];
        Muted = [NSColor colorWithCalibratedRed:0.42 green:0.43 blue:0.40 alpha:1];
        Sage = [NSColor colorWithCalibratedRed:0.49 green:0.56 blue:0.36 alpha:1];
        Mist = [NSColor colorWithCalibratedRed:0.52 green:0.68 blue:0.70 alpha:1];
        Terracotta = [NSColor colorWithCalibratedRed:0.69 green:0.31 blue:0.23 alpha:1];
        RenderFullSeriesBoard(workspace);
        RenderShelfThumbnailBoard(workspace);
        NSLog(@"Rendered selected Strategy B series to outputs/v1");
    }
    return 0;
}
