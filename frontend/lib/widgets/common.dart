import 'dart:math' as math;
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../data/sfx.dart';
import '../screens/shell.dart' show AppShell;

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

/// Web on a wide screen (desktop browser): use the whole window. Phones and
/// narrow windows keep the phone layout.
bool isWideWeb(BuildContext context) {
  // Wide layout (wheel on the left, tabs in the top bar): large windows, and
  // any landscape screen at least 560 px wide (phones turned sideways).
  final size = MediaQuery.sizeOf(context);
  return size.width >= 900 || (size.width > size.height && size.width >= 560);
}

/// Centres a page in a readable column on wide web; no change on phones.
class PageWidth extends StatelessWidget {
  final Widget child;
  final double max;
  PageWidth({super.key, required this.child, this.max = 860});
  @override
  Widget build(BuildContext context) =>
      MediaQuery.sizeOf(context).width > max
          // The page colour fills the whole window (no white bands); content stays readable.
          ? ColoredBox(color: kBg, child: Center(child: ConstrainedBox(constraints: BoxConstraints(maxWidth: max), child: child)))
          : child;
}

/// Top header shown on every main screen: current level with progress to the
/// next one, streak and Emeralds on the left, the user's avatar on the right
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
    // Ask this page's own navigator, not the router: an open sheet or dialog made the router
    // report "can go back" on top-level tabs, and tapping the arrow then threw an error.
    final nav = Navigator.of(context);
    // Same rule as Flutter's AppBar: only pages pushed on top of another page get a back arrow.
    final canPop = ModalRoute.of(context)?.impliesAppBarDismissal ?? false;
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
      title: Center(child: ConstrainedBox(
        // Same width and position on every page on wide screens.
        constraints: BoxConstraints(maxWidth: 1400),
        child: Row(children: [
        if (canPop) ...[
          IconButton(icon: Icon(Icons.arrow_back), tooltip: 'Back', onPressed: () => nav.maybePop()),
          SizedBox(width: 2),
        ],
        if (isWideWeb(context)) ...[
          _TopNav(),
          SizedBox(width: 12),
        ],
        Expanded(
          child: Semantics(
          container: true,
          button: true,
          excludeSemantics: true,
          label: '${lvl.name}, ${s.xp} Emeralds, ${s.streak} day streak. ${next == null ? 'Top level' : '${next.minXp - s.xp} Emeralds to ${next.name}'}. Open progress',
          child: GestureDetector(
          onTap: () => GoRouter.of(context).go('/progress'),
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
                  label: '${s.xp} Emeralds',
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
              Text(next == null ? 'Top level' : '${next.minXp - s.xp} Emeralds to ${next.name}', style: TextStyle(fontSize: 10, color: kMuted)),
            ]),
          ),
          ),
          ),
        ),
        SizedBox(width: 12),
        Semantics(
          container: true, // its own node: otherwise merged into the header and unreachable for screen readers
          button: true,
          label: 'Settings',
          excludeSemantics: true, // say "Settings", not the initial on the avatar
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
      )),
      bottom: PreferredSize(
        preferredSize: Size.fromHeight(title.isEmpty ? 10 : 50),
        child: title.isEmpty
            ? SizedBox(height: 10)
            : Container(
                alignment: Alignment.centerLeft,
                padding: EdgeInsets.fromLTRB(20, 0, 20, 14),
                child: Center(child: ConstrainedBox(constraints: BoxConstraints(maxWidth: 1000), child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                  Flexible(child: Text(title, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: kInk))),
                  if (subtitle != null) ...[
                    SizedBox(width: 8),
                    Padding(padding: EdgeInsets.only(bottom: 3), child: Text(subtitle!, style: TextStyle(fontSize: 13, color: kMuted))),
                  ],
                ]))),
              ),
      ),
    );
  }
}

/// Wide screens: the four tabs, in the top bar between the level card and the avatar.
class _TopNav extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final path = GoRouterState.of(context).uri.path;
    return Row(mainAxisSize: MainAxisSize.min, children: [
      for (final t in AppShell.tabs)
        Builder(builder: (context) {
          final on = path.startsWith(t.$1);
          return Padding(
            padding: EdgeInsets.symmetric(horizontal: 2),
            child: Semantics(
              container: true,
              button: true,
              selected: on,
              label: t.$4,
              excludeSemantics: true,
              child: Material(
                color: on ? kSurface : Colors.transparent,
                shape: StadiumBorder(side: BorderSide(color: on ? kWheelRim : Colors.transparent, width: 2)),
                child: InkWell(
                  customBorder: StadiumBorder(),
                  onTap: on
                      ? null
                      : () {
                          Sfx.tap();
                          GoRouter.of(context).go(t.$1);
                        },
                  child: Padding(
                    padding: EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    child: Row(mainAxisSize: MainAxisSize.min, children: [
                      Icon(on ? t.$3 : t.$2, size: 20, color: on ? kPrimaryText : kInk),
                      SizedBox(width: 6),
                      Text(t.$4, style: TextStyle(fontSize: 14, fontWeight: on ? FontWeight.w800 : FontWeight.w600, color: on ? kPrimaryText : kInk)),
                    ]),
                  ),
                ),
              ),
            ),
          );
        }),
      // Admin accounts only: a direct way into the admin panel.
      if (context.watch<AppState>().isAdmin)
        Padding(
          padding: EdgeInsets.only(left: 6),
          child: Semantics(
            button: true,
            label: 'Admin panel',
            excludeSemantics: true,
            child: Material(
              color: kWarnSoft,
              shape: StadiumBorder(side: BorderSide(color: kWarnBorder, width: 1.5)),
              child: InkWell(
                customBorder: StadiumBorder(),
                onTap: () => GoRouter.of(context).push('/admin'),
                child: Padding(
                  padding: EdgeInsets.symmetric(horizontal: 12, vertical: 9),
                  child: Row(mainAxisSize: MainAxisSize.min, children: [
                    Icon(Icons.admin_panel_settings_outlined, size: 19, color: kWarnText),
                    SizedBox(width: 6),
                    Text('Admin', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: kWarnText)),
                  ]),
                ),
              ),
            ),
          ),
        ),
    ]);
  }
}

/// Settings, opened from the avatar: appearance, accessibility, daily goal.
void showSettingsSheet(BuildContext context) {
  showModalBottomSheet(
    context: context,
    useRootNavigator: true, // above the tabs, so it never changes what the tab page thinks it can do
    isScrollControlled: true,
    constraints: BoxConstraints(maxWidth: 560), // a sheet, not a full-width banner, on wide screens
    // The sheet paints its own background (below) so it follows a theme switch
    // made from inside the sheet; a fixed backgroundColor would stay stale.
    backgroundColor: Colors.transparent,
    builder: (ctx) => Consumer<AppState>(builder: (ctx, s, _) {
      final p = s.profile;
      return AnimatedContainer(
        duration: Duration(milliseconds: 200),
        decoration: BoxDecoration(color: kBg, borderRadius: BorderRadius.vertical(top: Radius.circular(24))),
        child: SafeArea(
        child: Padding(
          padding: EdgeInsets.fromLTRB(20, 10, 20, 20),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Center(child: Container(width: 36, height: 4, margin: EdgeInsets.only(bottom: 14), decoration: BoxDecoration(color: kBorder, borderRadius: BorderRadius.circular(2)))),
            // Account: name (editable), how the user signed in, sign out.
            Row(children: [
              CircleAvatar(
                radius: 24,
                backgroundColor: kPrimarySoft,
                child: Text(p.name.isEmpty ? '?' : p.name[0].toUpperCase(),
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: kPrimaryText)),
              ),
              SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    Flexible(child: Text(p.name, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: kInk))),
                    IconButton(
                      tooltip: 'Edit name',
                      visualDensity: VisualDensity.compact,
                      icon: Icon(Icons.edit_outlined, size: 18, color: kPrimaryText),
                      onPressed: () => _editName(ctx, s),
                    ),
                  ]),
                  Text(
                    s.email ?? switch (s.signInMethod) { 'google' => 'Signed in with Google (demo)', 'guest' => 'Guest, not signed in', _ => 'Not signed in' },
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(color: kMuted),
                  ),
                ]),
              ),
            ]),
            SizedBox(height: 6),
            Text('Goal: ${p.goal} · ${p.horizonYears} years', style: TextStyle(color: kMuted, fontSize: 13)),
            if (s.isAdmin) ...[
              SizedBox(height: 10),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Icon(Icons.admin_panel_settings_outlined, color: kPrimaryText),
                title: Text('Admin panel'),
                subtitle: Text('Logs, events and tutor calls'),
                trailing: Icon(Icons.chevron_right),
                onTap: () {
                  Navigator.pop(ctx);
                  GoRouter.of(context).push('/admin');
                },
              ),
            ],
            if (s.email != null) ...[
              SizedBox(height: 10),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                value: s.shareProfile,
                title: Text('Share my learning profile with the bank', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
                subtitle: Text('Lets an adviser see your path, progress and how sure you felt, to start a conversation. '
                    'Off by default; you can turn it off any time.', style: TextStyle(fontSize: 12, color: kMuted)),
                onChanged: (v) async {
                  final before = s.shareProfile;
                  s.shareProfile = v;
                  s.notify();
                  try {
                    await s.api.setConsent(s.profile.name, v);
                  } catch (_) {
                    s.shareProfile = before;
                    s.notify();
                  }
                },
              ),
            ],
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
            // Sound effects: on by default; turning them on plays a short preview.
            Container(
              padding: EdgeInsets.fromLTRB(12, 10, 8, 10),
              decoration: BoxDecoration(
                gradient: s.soundOn ? LinearGradient(colors: [kPrimarySoft, kSurface]) : null,
                color: s.soundOn ? null : kSurface,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: s.soundOn ? kWheelRim : kLine, width: s.soundOn ? 2 : 1),
              ),
              child: Row(children: [
                AnimatedContainer(
                  duration: Duration(milliseconds: 200),
                  width: 40, height: 40,
                  decoration: BoxDecoration(shape: BoxShape.circle, color: s.soundOn ? kPrimary : kLine),
                  child: Icon(s.soundOn ? Icons.volume_up_rounded : Icons.volume_off_rounded, color: s.soundOn ? Colors.white : kFaint, size: 22),
                ),
                SizedBox(width: 12),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('Sound effects', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
                    Text(s.soundOn ? 'Ticks, answer chimes and badge fanfares' : 'Off: the app stays silent',
                        style: TextStyle(fontSize: 12, color: kMuted)),
                  ]),
                ),
                if (s.soundOn)
                  IconButton(tooltip: 'Play a sample', icon: Icon(Icons.play_circle_outline, color: kPrimaryText), onPressed: Sfx.correct),
                Switch(
                  value: s.soundOn,
                  onChanged: (v) {
                    s.setSound(v);
                    if (v) Sfx.correct();
                  },
                ),
              ]),
            ),
            SizedBox(height: 8),
            Row(children: [
              Text('Text size', style: TextStyle(color: kInk, fontSize: 16)),
              Spacer(),
              Text('${(s.textScale * 100).round()}%', style: TextStyle(color: kMuted, fontWeight: FontWeight.w700)),
            ]),
            Row(children: [
              Text('A', style: TextStyle(fontSize: 13, color: kMuted)),
              Expanded(
                child: Slider(
                  value: s.textScale,
                  min: 1.0,
                  max: 1.6,
                  divisions: 6,
                  label: '${(s.textScale * 100).round()}%',
                  semanticFormatterCallback: (v) => 'Text size ${(v * 100).round()} percent',
                  onChanged: s.setTextScale,
                ),
              ),
              Text('A', style: TextStyle(fontSize: 22, color: kMuted)),
            ]),
            SwitchListTile(contentPadding: EdgeInsets.zero, title: Text('List instead of the wheel'), value: s.listView, onChanged: s.setListView),
            SizedBox(height: 8),
            Text('Daily goal (Emeralds)', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
            SizedBox(height: 8),
            DailyGoalPicker(),
            SizedBox(height: 16),
            OutlinedButton.icon(
              icon: Icon(Icons.logout, color: kRed),
              label: Text(s.guest ? 'Leave guest mode' : 'Sign out', style: TextStyle(color: kRed)),
              style: OutlinedButton.styleFrom(minimumSize: Size.fromHeight(48), side: BorderSide(color: kRed.withValues(alpha: 0.5))),
              onPressed: () {
                Navigator.pop(ctx);
                s.signOut();
                GoRouter.of(context).go('/');
              },
            ),
          ]),
        ),
        ),
      );
    }),
  );
}

/// Edit the display name (shown in the header, the league and the tutor).
Future<void> _editName(BuildContext ctx, AppState s) async {
  final c = TextEditingController(text: s.profile.name);
  final name = await showDialog<String>(
    context: ctx,
    builder: (d) => AlertDialog(
      title: Text('Your name'),
      content: TextField(
        controller: c,
        autofocus: true,
        maxLength: 30,
        decoration: InputDecoration(labelText: 'Name shown in the app'),
        onSubmitted: (v) => Navigator.pop(d, v),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(d), child: Text('Cancel')),
        FilledButton(onPressed: () => Navigator.pop(d, c.text), child: Text('Save')),
      ],
    ),
  );
  if (name != null) s.rename(name);
}

/// Daily goal choice in Emeralds (used in settings and after the quick check).
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
/// The CrocoCash mascot, Kyle (assets/mascot/kyle, originals in docs/mascot/original).
/// Paulina's hand-drawn Kyle (pointing) is the default; the AI-made poses are used only
/// where the gesture means something: wave (hello), cheer/thumbs (well done) and
/// think/oops (a mistake, or "let's think it over"). Small sizes show Paulina's head.
/// The white-shirt art is used in light mode and the dark-shirt art in dark mode.
class MascotPlaceholder extends StatelessWidget {
  final double size; // height of the figure; under 90 it is the round head avatar
  final String? say; // optional speech bubble
  final String pose; // point | teach | read | wave | cheer | thumbs | think | oops
  final bool headOnPhone; // on narrow screens show the head avatar instead of the figure
  final VoidCallback? onTap; // e.g. open the tutor
  MascotPlaceholder({super.key, this.size = 64, this.say, this.pose = 'point', this.headOnPhone = false, this.onTap});

  static const _ai = {'wave': 'wave', 'hello': 'wave', 'cheer': 'thumbs', 'thumbs': 'thumbs', 'oops': 'think', 'think': 'think'};
  static const _files = ['point_light.webp', 'point_dark.webp', 'wave_light.webp', 'wave_dark.webp', 'thumbs_light.webp',
      'thumbs_dark.webp', 'think_dark.webp', 'head_light.png', 'head_dark.png'];

  static String fileFor(String pose, bool dark) {
    final t = dark ? 'dark' : 'light';
    final ai = _ai[pose];
    if (ai == null) return 'point_$t.webp';
    if (ai == 'think') return 'think_dark.webp'; // drawn in the dark shirt only; reads well on both themes
    return '${ai}_$t.webp';
  }

  /// Decode every pose once at start, so Kyle never pops in late.
  static void precache(BuildContext context) {
    for (final f in _files) {
      precacheImage(AssetImage('assets/mascot/kyle/$f'), context);
    }
  }

  @override
  Widget build(BuildContext context) {
    final phone = MediaQuery.sizeOf(context).width < 600;
    final asHead = size < 90 || (headOnPhone && phone);
    final h = asHead ? (size < 90 ? size : 56.0) : (phone ? size * 0.82 : size);
    final img = asHead
        ? Image.asset('assets/mascot/kyle/head_${appDark ? 'dark' : 'light'}.png',
            width: h, height: h, fit: BoxFit.contain, filterQuality: FilterQuality.medium)
        : Image.asset('assets/mascot/kyle/${fileFor(pose, appDark)}',
            height: h, width: h * 0.78, fit: BoxFit.contain, filterQuality: FilterQuality.medium);
    final face = Semantics(
      label: 'Kyle, the CrocoCash mascot',
      image: true,
      child: asHead ? ClipOval(child: ColoredBox(color: kPrimarySoft, child: img)) : img,
    );
    if (say == null) return _tappable(face);
    return _tappable(Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
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
    ]));
  }

  Widget _tappable(Widget w) => onTap == null
      ? w
      : Semantics(
          button: true,
          label: 'Ask Kyle, the tutor',
          child: MouseRegion(cursor: SystemMouseCursors.click, child: GestureDetector(behavior: HitTestBehavior.opaque, onTap: onTap, child: w)),
        );
}

/// The tutor, one tap away on every tab: a round button at the bottom right with Kyle's face.
/// Larger on big screens; on phones it sits above the bottom navigation.
class TutorFab extends StatelessWidget {
  TutorFab({super.key});

  @override
  Widget build(BuildContext context) {
    final big = MediaQuery.sizeOf(context).width >= 900;
    final d = big ? 66.0 : 58.0;
    return Semantics(
      button: true,
      label: 'Ask the tutor',
      excludeSemantics: true,
      child: Tooltip(
        message: 'Ask the tutor',
        child: Material(
          color: kPrimary,
          shape: CircleBorder(side: BorderSide(color: Colors.white, width: 3)),
          elevation: 6,
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: () => GoRouter.of(context).push('/tutor'),
            child: SizedBox(
              width: d, height: d,
              child: Stack(children: [
                Positioned.fill(child: Image.asset('assets/mascot/kyle/head_${appDark ? 'dark' : 'light'}.png', fit: BoxFit.cover)),
                Positioned(
                  right: 4, bottom: 4,
                  child: Container(
                    padding: EdgeInsets.all(3),
                    decoration: BoxDecoration(color: kPrimary, shape: BoxShape.circle, border: Border.all(color: Colors.white, width: 1.5)),
                    child: Icon(Icons.auto_awesome, size: big ? 14 : 12, color: Colors.white),
                  ),
                ),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}

/// Kyle with a short line of speech. Wide screens: the bubble sits above the full figure.
/// Phones: his round head avatar with the bubble beside it, so it never crowds the page.
class KyleCallout extends StatelessWidget {
  final String text;
  final String pose;
  final double size;
  final VoidCallback? onTap; // e.g. open the tutor: Kyle himself is the button
  final bool mirrored; // flip Kyle left to right (the text bubble stays readable)
  KyleCallout({super.key, required this.text, this.pose = 'point', this.size = 200, this.onTap, this.mirrored = false});

  @override
  Widget build(BuildContext context) {
    if (MediaQuery.sizeOf(context).width < 600) return MascotPlaceholder(size: 44, say: text);
    final body = Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.center, children: [
      ConstrainedBox(
        constraints: BoxConstraints(maxWidth: size * 0.95),
        child: Container(
          padding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(color: kSurface, borderRadius: BorderRadius.circular(14), border: Border.all(color: kBorder)),
          child: Text(text, textAlign: TextAlign.center, style: TextStyle(fontSize: 13, color: kBody, height: 1.3)),
        ),
      ),
      SizedBox(height: 4),
      mirrored ? Transform.flip(flipX: true, child: MascotPlaceholder(size: size, pose: pose)) : MascotPlaceholder(size: size, pose: pose),
    ]);
    if (onTap == null) return body;
    return Semantics(
      button: true,
      label: 'Ask Kyle, the tutor',
      child: Tooltip(
        message: 'Ask Kyle, the tutor',
        child: MouseRegion(cursor: SystemMouseCursors.click, child: GestureDetector(onTap: onTap, child: body)),
      ),
    );
  }
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

/// The written explanation after an answer: the team's written "why" for the question.
/// Kept separate from AI tutor prompts so it is clear it is human-written curriculum content.
class ExplanationBubble extends StatelessWidget {
  final String text;
  final String? title;
  ExplanationBubble({super.key, required this.text, this.title});

  @override
  Widget build(BuildContext context) => Panel(
        border: kBorder,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(Icons.lightbulb_outline, size: 18, color: kPrimaryText),
            SizedBox(width: 6),
            Text(title ?? 'Explanation', style: TextStyle(fontWeight: FontWeight.w700, color: kPrimaryText)),
          ]),
          SizedBox(height: 8),
          Text(text, style: TextStyle(height: 1.45, color: kBody)),
        ]),
      );
}

/// The suggestion to ask the AI tutor: opens the tutor chat with the crocodile mascot.
/// Sits in its own dedicated box, separate from the curriculum explanation.
class AskTutorBubble extends StatelessWidget {
  final VoidCallback onAsk;
  AskTutorBubble({super.key, required this.onAsk});

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        label: 'Ask the tutor about this',
        child: Material(
          color: kSurface,
          borderRadius: BorderRadius.circular(16),
          child: InkWell(
            borderRadius: BorderRadius.circular(16),
            onTap: onAsk,
            child: Container(
              padding: EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: kTutorBorder),
              ),
              child: Row(children: [
                MascotPlaceholder(size: 40, pose: 'teach'),
                SizedBox(width: 12),
                Expanded(
                  child: Text('Ask the tutor about this',
                      style: TextStyle(fontWeight: FontWeight.w700, color: kPrimaryText)),
                ),
                Icon(Icons.chevron_right, color: kPrimaryText),
              ]),
            ),
          ),
        ),
      );
}

/// Combined post-answer explanation and optional AI tutor redirection.
/// The explanation is kept separate from the tutor redirection tile.
class TutorBubble extends StatelessWidget {
  final String text;
  final VoidCallback? onAsk; // opens the tutor chat about this question
  TutorBubble({super.key, required this.text, this.onAsk});

  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ExplanationBubble(text: text),
          if (onAsk != null) ...[
            SizedBox(height: 10),
            AskTutorBubble(onAsk: onAsk!),
          ],
        ],
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
  bool _cached = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_cached) {
      _cached = true;
      MascotPlaceholder.precache(context);
    }
  }

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
          Sfx.badge();
          final b = badgeDefs.firstWhere((x) => x.id == id);
          await showDialog(
            context: ctx,
            builder: (d) => AlertDialog(
              title: Text('Badge earned', textAlign: TextAlign.center),
              content: Column(mainAxisSize: MainAxisSize.min, children: [
                Row(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.end, children: [
                  MascotPlaceholder(size: 150, pose: 'cheer'),
                  BadgeMedal(id: id, size: 84),
                ]),
                SizedBox(height: 14),
                Text(b.title, style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: kInk)),
                SizedBox(height: 4),
                Text(b.rule, textAlign: TextAlign.center, style: TextStyle(color: kMuted)),
              ]),
              actionsAlignment: MainAxisAlignment.center,
              actions: [FilledButton(style: FilledButton.styleFrom(minimumSize: Size(120, 44)), onPressed: () => Navigator.pop(d), child: Text('Nice'))],
            ),
          );
        }
        _showing = false;
      });
    }
    return widget.child;
  }
}
