import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';

// Palette from the Figma frames (docs/design/Lightmode.pdf and Darkmode.pdf):
// greens on white in light mode, greens on near-black in dark mode.
// [appDark] is set in main.dart from the user's appearance choice.
bool appDark = false;
Color _p(int light, int dark) => Color(appDark ? dark : light);
Color get kInk => _p(0xFF102A16, 0xFFF1F5EF);
Color get kMuted => _p(0xFF4A5E4F, 0xFFB3C2AE);
Color get kBody => _p(0xFF2F4334, 0xFFD5E0D1);
Color get kFaint => _p(0xFF9AAE9C, 0xFF7E8F7A);
const kPrimary = Color(0xFF0E8430); // buttons: white text on this passes contrast in both modes
Color get kPrimaryText => _p(0xFF0E6B27, 0xFF8CDE6E);
Color get kPrimarySoft => _p(0xFFE4F8DB, 0xFF26381F);
Color get kGreen => _p(0xFF0E8430, 0xFF8CDE6E);
Color get kGreenSoft => _p(0xFFE4F8DB, 0xFF1E3319);
Color get kRed => _p(0xFFB42318, 0xFFF87171);
Color get kRedSoft => _p(0xFFFEF3F2, 0xFF3A1717);
Color get kBg => _p(0xFFFFFFFF, 0xFF1D1D1D);
Color get kSurface => _p(0xFFFFFFFF, 0xFF262626);
Color get kLine => _p(0xFFD4EDCA, 0xFF314828);
Color get kBorder => _p(0xFFB8DDA8, 0xFF446039);
Color get kTutorBorder => _p(0xFF8DE46D, 0xFF47673C);
Color get kWarnSoft => _p(0xFFFFFAEB, 0xFF2E2510);
Color get kWarnBorder => _p(0xFFFDE68A, 0xFF6B5418);
Color get kWarnText => _p(0xFF93370D, 0xFFFCD34D);
Color get kWarnIcon => _p(0xFFB54708, 0xFFF59E0B);

// Wheel and header colours, taken from the frames.
Color get kTopGlow => _p(0xFF0E8430, 0xFF47673C); // header gradient start
Color get kBottomGlow => _p(0xFFAEFF90, 0xFF314828); // glow behind the wheel
Color get kWheelFace => _p(0xFF8DE46D, 0xFF8CDE6E);
Color get kWheelFaceSel => _p(0xFFA6F086, 0xFFA4EC88);
Color get kWheelLine => _p(0xFF6CC17B, 0xFF56973E);
Color get kWheelRim => _p(0xFF69C049, 0xFF56973E);
Color get kHub => _p(0xFF119B2A, 0xFF0E8430);
Color get kHubRim => _p(0xFF0E8430, 0xFF1A8F1E);
Color get kRimLabel => _p(0xFF0B4F1D, 0xFF0A0A0A);
Color get kRimLabelSel => _p(0xFFFFFFFF, 0xFF000000);
Color get kFaceLabel => _p(0xFF0B3D16, 0xFFFFFFFF);
Color get kNavBand => _p(0xFFB8EEA5, 0xFF47673C);

/// Risk colour scale: 1 calm (green) .. 5 bumpy (dark red).
Color riskColor(int risk) => [
      Color(0xFF1F7A55), Color(0xFF3D8B5E), Color(0xFF8A7A1E), Color(0xFFB8551A), Color(0xFF7F1D1D)
    ][(risk - 1).clamp(0, 4)];

/// Top header shown on every main screen: current level with progress to the
/// next one, streak and Scales on the left, the user's avatar on the right
/// (tap it for settings). A crocodile-back ridge runs along the bottom edge.
class StatsBar extends StatelessWidget implements PreferredSizeWidget {
  final String title;
  final String? subtitle;
  StatsBar({super.key, this.title = '', this.subtitle});

  static const double _row = 84;

  @override
  Size get preferredSize => Size.fromHeight(_row + (title.isEmpty ? 10 : 50));

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final lvl = s.level, next = s.nextLevel;
    final frac = next == null ? 1.0 : (s.xp - lvl.minXp) / (next.minXp - lvl.minXp);
    final initial = s.profile.name.isEmpty ? '?' : s.profile.name[0].toUpperCase();
    final canPop = GoRouter.of(context).canPop();
    return AppBar(
      toolbarHeight: _row,
      automaticallyImplyLeading: false,
      backgroundColor: Colors.transparent,
      surfaceTintColor: Colors.transparent,
      titleSpacing: 16,
      flexibleSpace: Stack(children: [
        Positioned.fill(
          child: DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [kTopGlow, kTopGlow.withValues(alpha: 0.35), kBg],
                stops: [0, 0.55, 1],
              ),
            ),
          ),
        ),
        Positioned(left: 0, right: 0, bottom: 0, height: 10, child: CustomPaint(painter: CrocoRidgePainter(kWheelRim.withValues(alpha: 0.5)))),
      ]),
      title: Row(children: [
        if (canPop) ...[
          IconButton(icon: Icon(Icons.arrow_back), tooltip: 'Back', onPressed: () => GoRouter.of(context).pop()),
          SizedBox(width: 2),
        ],
        Expanded(
          child: Container(
            padding: EdgeInsets.fromLTRB(14, 8, 12, 8),
            decoration: BoxDecoration(
              color: kSurface,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: kWheelRim, width: 2),
            ),
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(child: Text(lvl.name, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w800, color: kInk))),
                Semantics(
                  label: '${s.streak} day streak',
                  excludeSemantics: true,
                  child: Row(mainAxisSize: MainAxisSize.min, children: [
                    Icon(Icons.local_fire_department, size: 17, color: kWarnIcon),
                    SizedBox(width: 2),
                    Text('${s.streak}', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: kInk)),
                  ]),
                ),
                SizedBox(width: 10),
                Semantics(
                  label: '${s.xp} Scales',
                  excludeSemantics: true,
                  child: Row(mainAxisSize: MainAxisSize.min, children: [
                    ScaleIcon(size: 17),
                    SizedBox(width: 3),
                    Text('${s.xp}', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: kInk)),
                  ]),
                ),
              ]),
              SizedBox(height: 6),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(value: frac.clamp(0, 1).toDouble(), minHeight: 6, color: kGreen, backgroundColor: kLine),
              ),
              SizedBox(height: 2),
              Text(next == null ? 'Top level' : '${next.minXp - s.xp} Scales to ${next.name}', style: TextStyle(fontSize: 10, color: kMuted)),
            ]),
          ),
        ),
        SizedBox(width: 12),
        Semantics(
          button: true,
          label: 'Settings',
          child: GestureDetector(
            onTap: () => showSettingsSheet(context),
            child: Container(
              width: 54, height: 54,
              decoration: BoxDecoration(color: kSurface, borderRadius: BorderRadius.circular(14), border: Border.all(color: kWheelRim, width: 2)),
              alignment: Alignment.center,
              child: Text(initial, style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: kPrimaryText)),
            ),
          ),
        ),
      ]),
      bottom: PreferredSize(
        preferredSize: Size.fromHeight(title.isEmpty ? 10 : 50),
        child: title.isEmpty
            ? SizedBox(height: 10)
            : Container(
                alignment: Alignment.centerLeft,
                padding: EdgeInsets.fromLTRB(20, 0, 20, 14),
                child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                  Flexible(child: Text(title, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: kInk))),
                  if (subtitle != null) ...[
                    SizedBox(width: 8),
                    Padding(padding: EdgeInsets.only(bottom: 3), child: Text(subtitle!, style: TextStyle(fontSize: 13, color: kMuted))),
                  ],
                ]),
              ),
      ),
    );
  }
}

/// Settings, opened from the avatar: appearance, accessibility, daily goal.
void showSettingsSheet(BuildContext context) {
  showModalBottomSheet(
    context: context,
    showDragHandle: true,
    isScrollControlled: true,
    backgroundColor: kBg,
    builder: (ctx) => Consumer<AppState>(builder: (ctx, s, _) {
      final p = s.profile;
      return SafeArea(
        child: Padding(
          padding: EdgeInsets.fromLTRB(20, 0, 20, 20),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(p.name, style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: kInk)),
            Text('Goal: ${p.goal} · ${p.horizonYears} years', style: TextStyle(color: kMuted)),
            SizedBox(height: 16),
            Text('Appearance', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
            SizedBox(height: 8),
            SegmentedButton<String>(
              showSelectedIcon: false,
              segments: [
                ButtonSegment(value: 'system', icon: Icon(Icons.brightness_auto), label: Text('System')),
                ButtonSegment(value: 'light', icon: Icon(Icons.light_mode), label: Text('Light')),
                ButtonSegment(value: 'dark', icon: Icon(Icons.dark_mode), label: Text('Dark')),
              ],
              selected: {s.themeMode},
              onSelectionChanged: (v) => s.setThemeMode(v.first),
            ),
            SizedBox(height: 12),
            SwitchListTile(contentPadding: EdgeInsets.zero, title: Text('Larger text'), value: s.largeText, onChanged: s.setLargeText),
            SwitchListTile(contentPadding: EdgeInsets.zero, title: Text('List instead of the wheel'), value: s.listView, onChanged: s.setListView),
            SizedBox(height: 8),
            Text('Daily goal (Scales)', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
            SizedBox(height: 8),
            DailyGoalPicker(),
          ]),
        ),
      );
    }),
  );
}

/// Daily goal choice in Scales (used in settings and after the quick check).
class DailyGoalPicker extends StatelessWidget {
  DailyGoalPicker({super.key});
  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    return SegmentedButton<int>(
      showSelectedIcon: false,
      segments: [for (final v in [30, 50, 100]) ButtonSegment(value: v, label: Text('$v'))],
      selected: {s.dailyGoal},
      onSelectionChanged: (v) => s.setDailyGoal(v.first),
    );
  }
}

/// The CrocoCash point: a crocodile scale (a rounded scute with a ridge).
class ScaleIcon extends StatelessWidget {
  final double size;
  ScaleIcon({super.key, this.size = 18});
  @override
  Widget build(BuildContext context) => CustomPaint(size: Size(size, size), painter: _ScalePainter());
}

class _ScalePainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, h = size.height;
    final body = Path()
      ..moveTo(w * 0.5, h * 0.04)
      ..quadraticBezierTo(w * 0.98, h * 0.18, w * 0.92, h * 0.55)
      ..quadraticBezierTo(w * 0.82, h * 0.92, w * 0.5, h * 0.98)
      ..quadraticBezierTo(w * 0.18, h * 0.92, w * 0.08, h * 0.55)
      ..quadraticBezierTo(w * 0.02, h * 0.18, w * 0.5, h * 0.04)
      ..close();
    canvas.drawPath(body, Paint()..color = Color(0xFF3FAE3A));
    canvas.drawPath(body, Paint()..color = Color(0xFF0E6B27)..style = PaintingStyle.stroke..strokeWidth = w * 0.08);
    canvas.drawLine(Offset(w * 0.5, h * 0.2), Offset(w * 0.5, h * 0.8), Paint()..color = Color(0xFF0E6B27)..strokeWidth = w * 0.09..strokeCap = StrokeCap.round);
    canvas.drawCircle(Offset(w * 0.32, h * 0.34), w * 0.08, Paint()..color = Colors.white.withValues(alpha: 0.7));
  }
  @override
  bool shouldRepaint(covariant CustomPainter old) => false;
}

/// A row of rounded crocodile-back bumps, used as a decorative edge.
class CrocoRidgePainter extends CustomPainter {
  final Color color;
  CrocoRidgePainter(this.color);
  @override
  void paint(Canvas canvas, Size size) {
    final bump = size.height * 2.2;
    final path = Path()..moveTo(0, size.height);
    for (double x = 0; x < size.width + bump; x += bump) {
      path.quadraticBezierTo(x + bump / 2, -size.height * 0.4, x + bump, size.height);
    }
    path
      ..lineTo(size.width, size.height)
      ..close();
    canvas.drawPath(path, Paint()..color = color);
  }
  @override
  bool shouldRepaint(covariant CrocoRidgePainter old) => old.color != color;
}

/// Draws two croco eye bumps sitting on a baseline at [base], total [width].
void paintCrocoEyes(Canvas canvas, Offset base, double width, Color skin) {
  final r = width * 0.22;
  for (final dx in [-width * 0.26, width * 0.26]) {
    final c = Offset(base.dx + dx, base.dy - r * 0.55);
    canvas.drawCircle(c, r, Paint()..color = skin);
    canvas.drawCircle(c, r, Paint()..color = Color(0xFF0B4F1D)..style = PaintingStyle.stroke..strokeWidth = r * 0.12);
    canvas.drawOval(Rect.fromCenter(center: c.translate(0, -r * 0.08), width: r * 1.15, height: r * 0.95), Paint()..color = Color(0xFFFFF4C2));
    canvas.drawOval(Rect.fromCenter(center: c.translate(0, -r * 0.08), width: r * 0.22, height: r * 0.8), Paint()..color = Color(0xFF111111));
    canvas.drawCircle(c.translate(-r * 0.25, -r * 0.32), r * 0.12, Paint()..color = Colors.white);
  }
}

/// A crocodile peeking over an edge (decoration).
class CrocoEyes extends StatelessWidget {
  final double width;
  CrocoEyes({super.key, this.width = 64});
  @override
  Widget build(BuildContext context) => CustomPaint(size: Size(width, width * 0.42), painter: _EyesPainter());
}

class _EyesPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) => paintCrocoEyes(canvas, Offset(size.width / 2, size.height), size.width, kHub);
  @override
  bool shouldRepaint(covariant CustomPainter old) => true;
}

/// Placeholder for the future mascot, so we can see how much space it takes.
/// A dashed outline with a simple face; swap the inside for the real artwork.
class MascotPlaceholder extends StatelessWidget {
  final double size;
  final String? say; // optional speech bubble
  MascotPlaceholder({super.key, this.size = 64, this.say});

  @override
  Widget build(BuildContext context) {
    final face = Semantics(
      label: 'Mascot placeholder',
      child: CustomPaint(
        painter: _DashedRRect(kWheelRim),
        child: Container(
          width: size, height: size,
          decoration: BoxDecoration(color: kPrimarySoft, borderRadius: BorderRadius.circular(size * 0.3)),
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            Icon(Icons.cruelty_free_outlined, size: size * 0.5, color: kPrimaryText),
            if (size >= 56) Text('mascot', style: TextStyle(fontSize: (size * 0.13).clamp(8, 13).toDouble(), color: kMuted)),
          ]),
        ),
      ),
    );
    if (say == null) return face;
    return Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
      face,
      SizedBox(width: 8),
      Flexible(
        child: Container(
          padding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: kSurface,
            borderRadius: BorderRadius.only(
              topLeft: Radius.circular(4), topRight: Radius.circular(14),
              bottomLeft: Radius.circular(14), bottomRight: Radius.circular(14),
            ),
            border: Border.all(color: kBorder),
          ),
          child: Text(say!, style: TextStyle(fontSize: 13, color: kBody, height: 1.3)),
        ),
      ),
    ]);
  }
}

class _DashedRRect extends CustomPainter {
  final Color color;
  _DashedRRect(this.color);
  @override
  void paint(Canvas canvas, Size size) {
    final path = Path()..addRRect(RRect.fromRectAndRadius(Offset.zero & size, Radius.circular(size.width * 0.3)));
    final paint = Paint()..color = color..style = PaintingStyle.stroke..strokeWidth = 2;
    for (final m in path.computeMetrics()) {
      for (double d = 0; d < m.length; d += 9) {
        canvas.drawPath(m.extractPath(d, math.min(d + 5, m.length)), paint);
      }
    }
  }
  @override
  bool shouldRepaint(covariant _DashedRRect old) => old.color != color;
}

/// Rounded white card used for panels.
class Panel extends StatelessWidget {
  final Widget child;
  final Color? color;
  final Color? border;
  Panel({super.key, required this.child, this.color, this.border});

  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: color ?? kSurface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: border ?? kLine),
        ),
        child: child,
      );
}

/// The AI tutor bubble. In the real app the text comes from POST /tutor
/// (Gemini, education only, labelled as AI); here it shows the stored "why".
class TutorBubble extends StatelessWidget {
  final String text;
  TutorBubble({super.key, required this.text});

  @override
  Widget build(BuildContext context) => Panel(
        border: kTutorBorder,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            MascotPlaceholder(size: 36),
            SizedBox(width: 8),
            Text('AI tutor', style: TextStyle(fontWeight: FontWeight.w700, color: kPrimaryText)),
            Spacer(),
            Text('Educational, not advice', style: TextStyle(fontSize: 11, color: kMuted)),
          ]),
          SizedBox(height: 6),
          Text(text, style: TextStyle(height: 1.45, color: kBody)),
        ]),
      );
}

/// The four-colour Google "G", drawn so no image asset is needed.
class GoogleG extends StatelessWidget {
  final double size;
  GoogleG({super.key, this.size = 20});
  @override
  Widget build(BuildContext context) => CustomPaint(size: Size(size, size), painter: _GooglePainter());
}

class _GooglePainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final s = size.width, sw = s * 0.2, c = Offset(s / 2, s / 2), r = s / 2 - sw / 2;
    final box = Rect.fromCircle(center: c, radius: r);
    double d(double deg) => deg * math.pi / 180;
    Paint p(int color) => Paint()..color = Color(color)..style = PaintingStyle.stroke..strokeWidth = sw;
    canvas.drawArc(box, d(-45), d(-135), false, p(0xFFEA4335)); // red: top, opening on the upper right
    canvas.drawArc(box, d(180), d(-50), false, p(0xFFFBBC05)); // yellow: left
    canvas.drawArc(box, d(130), d(-85), false, p(0xFF34A853)); // green: bottom
    canvas.drawArc(box, d(45), d(-45), false, p(0xFF4285F4)); // blue: lower right
    // Blue bar from the centre to the right edge.
    canvas.drawRect(Rect.fromLTRB(s / 2, s / 2 - sw / 2, s - sw * 0.05, s / 2 + sw / 2), Paint()..color = Color(0xFF4285F4));
  }
  @override
  bool shouldRepaint(covariant CustomPainter old) => false;
}

// ---- Badges: one icon and colour per badge, and a pop-up when one is earned.
const badgeIcons = {
  'first_steps': Icons.flag_rounded,
  'placement': Icons.explore_rounded,
  'goal': Icons.track_changes_rounded,
};
const badgeColors = {
  'first_steps': Color(0xFF0E8430),
  'placement': Color(0xFF2E6FD8),
  'goal': Color(0xFFE08A00),
};

class BadgeMedal extends StatelessWidget {
  final String id;
  final bool earned;
  final double size;
  BadgeMedal({super.key, required this.id, this.earned = true, this.size = 44});
  @override
  Widget build(BuildContext context) => Container(
        width: size, height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: earned ? badgeColors[id] : kLine,
          border: Border.all(color: earned ? Colors.white : kBorder, width: 2),
          boxShadow: earned ? [BoxShadow(color: (badgeColors[id] ?? kPrimary).withValues(alpha: 0.35), blurRadius: 8)] : null,
        ),
        child: Icon(badgeIcons[id] ?? Icons.emoji_events, size: size * 0.52, color: earned ? Colors.white : kFaint),
      );
}

/// Shows "Badge earned" whenever AppState queues one. Lives above the router
/// (MaterialApp builder) and uses the root navigator's context.
class BadgeWatcher extends StatefulWidget {
  final Widget child;
  final GlobalKey<NavigatorState> navigatorKey;
  BadgeWatcher({super.key, required this.child, required this.navigatorKey});
  @override
  State<BadgeWatcher> createState() => _BadgeWatcherState();
}

class _BadgeWatcherState extends State<BadgeWatcher> {
  bool _showing = false;

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final id = s.pendingBadge;
    if (id != null && !_showing) {
      _showing = true;
      WidgetsBinding.instance.addPostFrameCallback((_) async {
        final ctx = widget.navigatorKey.currentContext;
        s.clearPendingBadge();
        if (ctx != null) {
          final b = badgeDefs.firstWhere((x) => x.id == id);
          await showDialog(
            context: ctx,
            builder: (d) => AlertDialog(
              title: Text('Badge earned', textAlign: TextAlign.center),
              content: Column(mainAxisSize: MainAxisSize.min, children: [
                BadgeMedal(id: id, size: 84),
                SizedBox(height: 14),
                Text(b.title, style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: kInk)),
                SizedBox(height: 4),
                Text(b.rule, textAlign: TextAlign.center, style: TextStyle(color: kMuted)),
              ]),
              actionsAlignment: MainAxisAlignment.center,
              actions: [FilledButton(onPressed: () => Navigator.pop(d), child: Text('Nice'))],
            ),
          );
        }
        _showing = false;
      });
    }
    return widget.child;
  }
}
