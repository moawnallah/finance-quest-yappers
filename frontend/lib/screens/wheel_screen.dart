// Home (layout from the Figma frames in docs/design/): the user's header on
// top, the roadmap of the selected skills-tree panel in the middle, and a
// spinnable wheel of panels at the bottom. Missions are the skills from the
// backend (GET /skills) with their real prerequisites; locked ones can still be
// started after a warning. The roadmap header hides while you scroll.
// List view (settings) replaces the wheel with simple chips.

import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../data/sfx.dart';
import '../widgets/common.dart';
import 'skills_screen.dart' show ErrorPanel;

/// Lora, resolved once (GoogleFonts lookups are slow inside paint).
// One lookup per weight (each weight is its own font file), then plain TextStyles.
final Map<FontWeight?, TextStyle> _loraBase = {};
TextStyle _lora({double? fontSize, FontWeight? fontWeight, Color? color, double? letterSpacing, double? height}) =>
    (_loraBase[fontWeight] ??= GoogleFonts.lora(fontWeight: fontWeight))
        .copyWith(fontSize: fontSize, color: color, letterSpacing: letterSpacing, height: height);

class WheelScreen extends StatefulWidget {
  WheelScreen({super.key});
  @override
  State<WheelScreen> createState() => _WheelScreenState();
}

class _WheelScreenState extends State<WheelScreen> {
  static const headerH = 92.0;
  bool _headerVisible = true;
  Timer? _showAgain;
  DateTime _quietUntil = DateTime.now().add(Duration(milliseconds: 900));
  String? _shownPanel;

  @override
  void initState() {
    super.initState();
    final s = context.read<AppState>();
    if (s.skills.isEmpty && !s.skillsLoading) WidgetsBinding.instance.addPostFrameCallback((_) => s.loadSkills());
  }

  @override
  void dispose() {
    _showAgain?.cancel();
    super.dispose();
  }

  // Hide the roadmap header while the user scrolls; bring it back when they stop.
  bool _onScroll(ScrollNotification n) {
    if (n.depth != 0) return false;
    // Relayouts (opening the tab, switching topic) also send scroll events; ignore them.
    if (DateTime.now().isBefore(_quietUntil)) return false;
    if (n is ScrollUpdateNotification && (n.scrollDelta ?? 0).abs() > 0.5) {
      // any real movement (finger, mouse wheel, trackpad) hides the header
      _showAgain?.cancel();
      if (_headerVisible) setState(() => _headerVisible = false);
      _showAgain = Timer(Duration(milliseconds: 900), () {
        if (mounted) setState(() => _headerVisible = true);
      });
    } else if (n is ScrollEndNotification) {
      _showAgain?.cancel();
      _showAgain = Timer(Duration(milliseconds: 700), () {
        if (mounted) setState(() => _headerVisible = true);
      });
    }
    return false;
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    if (_shownPanel != s.selectedPanel) {
      // A new topic: show its header and ignore the relayout that follows.
      _shownPanel = s.selectedPanel;
      _headerVisible = true;
      _showAgain?.cancel();
      _quietUntil = DateTime.now().add(Duration(milliseconds: 700));
    }
    Widget body;
    if (s.skills.isEmpty && s.skillsLoading) {
      body = Center(child: CircularProgressIndicator());
    } else if (s.skills.isEmpty && s.skillsError != null) {
      body = ListView(padding: EdgeInsets.all(20), children: [ErrorPanel(message: s.skillsError!, onRetry: s.loadSkills)]);
    } else if (s.skills.isEmpty) {
      body = Center(child: Text('No missions yet.', style: TextStyle(color: kMuted)));
    } else {
      body = LayoutBuilder(builder: (context, c) {
        if (isWideWeb(context) && !s.listView) return _wide(context, s, c);
        final w = c.maxWidth;
        final wheelH = s.listView ? 132.0 : math.min(w * 0.66, c.maxHeight * 0.5);
        final panel = s.selectedPanel;
        return Stack(children: [
          NotificationListener<ScrollNotification>(
            onNotification: _onScroll,
            child: RefreshIndicator(
              onRefresh: s.loadSkills,
              child: SingleChildScrollView(
                reverse: true, // starts at the bottom: the wheel and the first missions
                physics: AlwaysScrollableScrollPhysics(),
                child: ConstrainedBox(
                  constraints: BoxConstraints(minHeight: c.maxHeight),
                  child: Column(mainAxisAlignment: MainAxisAlignment.end, children: [
                    SizedBox(height: headerH),
                    AnimatedSize(
                      duration: Duration(milliseconds: 300),
                      curve: Curves.easeOutCubic,
                      alignment: Alignment.bottomCenter,
                      child: AnimatedSwitcher(
                        duration: Duration(milliseconds: 380),
                        switchInCurve: Curves.easeOutCubic,
                        switchOutCurve: Curves.easeInCubic,
                        layoutBuilder: (cur, prev) => Stack(alignment: Alignment.bottomCenter, children: [...prev, if (cur != null) cur]),
                        transitionBuilder: (child, a) => FadeTransition(
                          opacity: a,
                          child: SlideTransition(position: Tween(begin: Offset(0, 0.04), end: Offset.zero).animate(a), child: child),
                        ),
                        child: _Tree(key: ValueKey(panel), panel: panel),
                      ),
                    ),
                    if (s.skillsIn(panel).isNotEmpty && s.plannedIn(panel).isNotEmpty)
                      Padding(padding: EdgeInsets.fromLTRB(16, 0, 16, 8), child: _PlannedStrip(panel: panel)),
                    Padding(
                      padding: EdgeInsets.fromLTRB(16, 0, 16, 6),
                      child: MascotPlaceholder(
                        size: 44,
                        say: s.skillsIn(panel).isEmpty ? 'These missions are coming later. Tap one to see where it fits.' : 'Tap a glowing mission to start learning.',
                      ),
                    ),
                    Container(
                      height: wheelH,
                      decoration: BoxDecoration(
                        gradient: RadialGradient(
                          center: Alignment(0, 1.3),
                          radius: 1.1,
                          colors: [kBottomGlow, kBottomGlow.withValues(alpha: 0.3), kBg],
                          stops: [0, 0.55, 1],
                        ),
                      ),
                      child: s.listView ? _PanelPicker() : _SpinWheel(key: ValueKey(s.panels.join()), panels: s.panels),
                    ),
                  ]),
                ),
              ),
            ),
          ),
          // Roadmap header: shown when the roadmap opens, hidden while scrolling.
          Positioned(
            left: 0, right: 0, top: 0, height: headerH,
            child: IgnorePointer(
              ignoring: !_headerVisible,
              child: AnimatedSlide(
                offset: _headerVisible ? Offset.zero : Offset(0, -1),
                duration: Duration(milliseconds: 250),
                curve: Curves.easeOutCubic,
                child: AnimatedOpacity(
                  opacity: _headerVisible ? 1 : 0,
                  duration: Duration(milliseconds: 200),
                  child: AnimatedSwitcher(
                    duration: Duration(milliseconds: 250),
                    child: _RoadmapHeader(key: ValueKey(panel), panel: panel),
                  ),
                ),
              ),
            ),
          ),
        ]);
      });
    }
    return Scaffold(backgroundColor: kBg, appBar: StatsBar(), body: body);
  }
}

// ---------------------------------------------------------------------------

extension on _WheelScreenState {
  /// Desktop browser: the wheel sits on the left edge (pointer facing right),
  /// the roadmap and its header take the rest of the window.
  Widget _wide(BuildContext context, AppState s, BoxConstraints c) {
    final r = math.min(c.maxHeight * 0.46, c.maxWidth * 0.3);
    final wheelW = r * 1.08 + 30;
    final panel = s.selectedPanel;
    return Row(children: [
      Container(
        width: wheelW,
        decoration: BoxDecoration(
          gradient: RadialGradient(
            center: Alignment(-1.3, 0),
            radius: 1.2,
            colors: [kBottomGlow, kBottomGlow.withValues(alpha: 0.3), kBg],
            stops: [0, 0.55, 1],
          ),
        ),
        child: _SpinWheel(key: ValueKey('left${s.panels.join()}'), panels: s.panels, left: true),
      ),
      Expanded(
        child: LayoutBuilder(builder: (context, rc) {
          // Kyle stands in the roadmap's corner; the roadmap keeps clear of him.
          final kyle = (rc.maxHeight * 0.44).clamp(160.0, 340.0);
          final showKyle = rc.maxHeight >= 380 && rc.maxWidth >= 560;
          final kyleW = showKyle ? kyle * 0.78 + 40 : 0.0;
          return Stack(children: [
          NotificationListener<ScrollNotification>(
            onNotification: _onScroll,
            child: Column(children: [
              SizedBox(height: _WheelScreenState.headerH),
              Expanded(
                child: Stack(children: [
                  Positioned(left: 0, top: 0, bottom: 0, right: kyleW, child: s.skillsIn(panel).isEmpty
                    ? Center(child: _Tree(key: ValueKey(panel), panel: panel))
                    : LayoutBuilder(builder: (context, tc) => SingleChildScrollView(child: SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: ConstrainedBox(
                    constraints: BoxConstraints(minWidth: tc.maxWidth),
                    child: AnimatedSwitcher(
                      duration: Duration(milliseconds: 380),
                      switchInCurve: Curves.easeOutCubic,
                      layoutBuilder: (cur, prev) => Stack(alignment: Alignment.centerLeft, children: [...prev, if (cur != null) cur]),
                      transitionBuilder: (child, a) => FadeTransition(
                        opacity: a,
                        child: SlideTransition(position: Tween(begin: Offset(-0.03, 0), end: Offset.zero).animate(a), child: child),
                      ),
                      child: Align(
                        key: ValueKey(panel),
                        alignment: Alignment.centerLeft,
                        child: _Tree(panel: panel, horizontal: true, height: tc.maxHeight - 16),
                      ),
                    ),
                  ),
                )))),
                  // Coming-later topics of this panel, in their own colour.
                  if (s.skillsIn(panel).isNotEmpty && s.plannedIn(panel).isNotEmpty)
                    Positioned(left: 16, right: kyleW, bottom: 10, child: _PlannedStrip(panel: panel)),
                  // Kyle points the way, sized to the window.
                  if (showKyle)
                    Positioned(
                      right: 16,
                      bottom: 8,
                      child: IgnorePointer(
                        child: KyleCallout(
                          size: kyle,
                          text: s.skillsIn(panel).isEmpty ? 'These missions are coming later. Tap one to see where it fits.' : 'Tap a glowing mission to start learning.',
                        ),
                      ),
                    ),
                ]),
              ),
            ]),
          ),
          Positioned(
            left: 0, right: 0, top: 0, height: _WheelScreenState.headerH,
            child: IgnorePointer(
              ignoring: !_headerVisible,
              child: AnimatedSlide(
                offset: _headerVisible ? Offset.zero : Offset(0, -1),
                duration: Duration(milliseconds: 250),
                curve: Curves.easeOutCubic,
                child: AnimatedOpacity(
                  opacity: _headerVisible ? 1 : 0,
                  duration: Duration(milliseconds: 200),
                  child: AnimatedSwitcher(duration: Duration(milliseconds: 250), child: _RoadmapHeader(key: ValueKey(panel), panel: panel)),
                ),
              ),
            ),
          ),
        ]);
        }),
      ),
    ]);
  }
}

class _RoadmapHeader extends StatelessWidget {
  final String panel;
  _RoadmapHeader({super.key, required this.panel});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final ks = s.skillsIn(panel);
    final done = ks.where(s.skillDone).length;
    final prog = s.panelProgress(panel);
    final focus = s.focusSlices.contains(panel);
    return Container(
      color: kBg,
      padding: EdgeInsets.fromLTRB(20, 4, 12, 8),
      child: Row(children: [
        Expanded(
          child: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(panelLabels[panel] ?? panel, style: _lora(fontSize: 24, fontWeight: FontWeight.w700, color: kInk, height: 1.1)),
            SizedBox(height: 2),
            Text(panelQuestions[panel] ?? '', maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 13, color: kBody)),
            Text(ks.isEmpty ? 'Coming later: ${s.plannedIn(panel).length} missions planned' : '$done of ${ks.length} missions done${focus ? ' · your focus' : ''}', style: TextStyle(fontSize: 12, color: kMuted)),
          ]),
        ),
        Semantics(
          label: '${(prog * 100).round()} percent of ${panelLabels[panel]} done',
          excludeSemantics: true,
          child: SizedBox(
            width: 46, height: 46,
            child: Stack(alignment: Alignment.center, children: [
              TweenAnimationBuilder<double>(
                tween: Tween(begin: 0, end: prog),
                duration: Duration(milliseconds: 600),
                curve: Curves.easeOutCubic,
                builder: (_, v, __) => CircularProgressIndicator(value: v, strokeWidth: 5, color: kGreen, backgroundColor: kLine),
              ),
              Text('${(prog * 100).round()}%', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: kInk)),
            ]),
          ),
        ),
        if (!s.dailyAnswered)
          IconButton(
            tooltip: "Today's question, +${Rewards.dailyRight} Scales",
            icon: Icon(Icons.today, color: kWarnIcon),
            onPressed: () => showDailyQuestion(context),
          ),
      ]),
    );
  }
}

// ---------------------------------------------------------------------------
// Roadmap: the panel's skills as branching trails growing out of the wheel.
// A mission's depth is its longest chain of prerequisites inside the panel.

class _Tree extends StatelessWidget {
  final String panel;
  final bool horizontal; // wide screens: grows left to right out of the wheel
  final double? height; // horizontal mode: the height to spread missions over
  _Tree({super.key, required this.panel, this.horizontal = false, this.height});

  static const rowH = 112.0, pad = 40.0;

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final ks = s.skillsIn(panel);
    if (ks.isEmpty && s.plannedIn(panel).isNotEmpty) return _Planned(panel: panel, horizontal: horizontal);
    if (ks.isEmpty) {
      return Padding(
        padding: EdgeInsets.fromLTRB(32, 40, 32, 48),
        child: Column(children: [
          Icon(Icons.construction_rounded, size: 40, color: kFaint),
          SizedBox(height: 10),
          Text('Missions for ${panelLabels[panel]} are coming soon.', textAlign: TextAlign.center,
              style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: kInk)),
          SizedBox(height: 4),
          Text(panelQuestions[panel] ?? '', textAlign: TextAlign.center, style: TextStyle(color: kMuted)),
        ]),
      );
    }
    final ids = {for (final k in ks) k['id'] as String};
    final byId = {for (final k in ks) k['id'] as String: k};
    List<String> inPanel(Map<String, dynamic> k) => [for (final a in s.knownAfter(k)) if (ids.contains(a)) a];
    final depth = <String, int>{};
    int d(Map<String, dynamic> k) =>
        depth[k['id'] as String] ??= inPanel(k).isEmpty ? 0 : 1 + inPanel(k).map((a) => d(byId[a]!)).fold(0, math.max);
    for (final k in ks) {
      d(k);
    }
    final rows = <int, List<Map<String, dynamic>>>{};
    for (final k in ks) {
      rows.putIfAbsent(depth[k['id']]!, () => []).add(k);
    }
    final maxDepth = rows.keys.fold(0, math.max);
    if (horizontal) return _horizontal(context, s, ks, rows, maxDepth, inPanel);
    final h = pad * 2 + maxDepth * rowH + 70;

    return LayoutBuilder(builder: (context, c) {
      final w = c.maxWidth;
      final pos = <String, Offset>{};
      for (final MapEntry(key: r, value: list) in rows.entries) {
        for (final (i, k) in list.indexed) {
          final x = list.length == 1 ? w * (r.isEven ? 0.38 : 0.62) : w * (i + 1) / (list.length + 1);
          pos[k['id'] as String] = Offset(x, h - pad - 26 - r * rowH);
        }
      }
      return SizedBox(
        width: w,
        height: h,
        child: Stack(clipBehavior: Clip.none, children: [
          Positioned.fill(child: CustomPaint(painter: _PathsPainter(ks, pos, s, inPanel, Offset(w / 2, h + 8)))),
          for (final k in ks)
            Positioned(
              left: pos[k['id']]!.dx - 56,
              top: pos[k['id']]!.dy - 30,
              width: 112,
              child: _MissionNode(skill: k),
            ),
        ]),
      );
    });
  }

  Widget _horizontal(BuildContext context, AppState s, List<Map<String, dynamic>> ks, Map<int, List<Map<String, dynamic>>> rows,
      int maxDepth, List<String> Function(Map<String, dynamic>) inPanel) {
    const colW = 210.0, lead = 120.0;
    // At least ~125 px per mission in a column, so short (landscape) screens never overlap; the area scrolls.
    final perCol = rows.values.map((l) => l.length).fold(1, math.max);
    final h = math.max(height ?? 400, perCol * 160.0 + 40);
    final w = lead + maxDepth * colW + 140;
    final pos = <String, Offset>{};
    for (final MapEntry(key: c, value: list) in rows.entries) {
      for (final (i, k) in list.indexed) {
        final y = list.length == 1 ? h * (c.isEven ? 0.45 : 0.58) : h * (i + 1) / (list.length + 1);
        pos[k['id'] as String] = Offset(lead + c * colW, y);
      }
    }
    return SizedBox(
      width: w,
      height: h,
      child: Stack(clipBehavior: Clip.none, children: [
        Positioned.fill(child: CustomPaint(painter: _PathsPainter(ks, pos, s, inPanel, Offset(-12, h / 2), horizontal: true))),
        for (final k in ks)
          Positioned(left: pos[k['id']]!.dx - 56, top: pos[k['id']]!.dy - 30, width: 112, child: _MissionNode(skill: k)),
      ]),
    );
  }
}

class _PathsPainter extends CustomPainter {
  final List<Map<String, dynamic>> ks;
  final Map<String, Offset> pos;
  final AppState s;
  final List<String> Function(Map<String, dynamic>) inPanel;
  final Offset root;
  final bool horizontal;
  _PathsPainter(this.ks, this.pos, this.s, this.inPanel, this.root, {this.horizontal = false});

  void _trail(Canvas canvas, Offset a, Offset b, bool walked) {
    final path = Path()..moveTo(a.dx, a.dy);
    if (horizontal) {
      final dx = (b.dx - a.dx).abs() * 0.55;
      path.cubicTo(a.dx + dx, a.dy, b.dx - dx, b.dy, b.dx, b.dy);
    } else {
      final dy = (a.dy - b.dy).abs() * 0.55;
      path.cubicTo(a.dx, a.dy - dy, b.dx, b.dy + dy, b.dx, b.dy);
    }
    canvas.drawPath(path, Paint()..color = (walked ? kWheelRim : kLine)..style = PaintingStyle.stroke..strokeWidth = 14..strokeCap = StrokeCap.round);
    final dash = Paint()..color = walked ? Colors.white.withValues(alpha: 0.85) : kBorder..style = PaintingStyle.stroke..strokeWidth = 2.5..strokeCap = StrokeCap.round;
    for (final m in path.computeMetrics()) {
      for (double t = 0; t < m.length; t += 12) {
        canvas.drawPath(m.extractPath(t, math.min(t + 5, m.length)), dash);
      }
    }
  }

  @override
  void paint(Canvas canvas, Size size) {
    for (final k in ks) {
      final p = pos[k['id']]!;
      final inside = inPanel(k);
      if (inside.isEmpty) _trail(canvas, root, p, true); // the trunk grows out of the wheel
      for (final a in inside) {
        _trail(canvas, pos[a]!, p, s.skillDone(s.skillById(a)!));
      }
    }
  }

  @override
  bool shouldRepaint(covariant _PathsPainter old) => true;
}

class _MissionNode extends StatelessWidget {
  final Map<String, dynamic> skill;
  _MissionNode({required this.skill});

  Future<void> _open(BuildContext context) async {
    final s = context.read<AppState>();
    final id = skill['id'] as String;
    if (s.skillState(skill) == 'locked') {
      final missing = [for (final a in s.knownAfter(skill)) if (!s.skillDone(s.skillById(a)!)) s.skillById(a)!];
      final go = await showDialog<bool>(
        context: context,
        builder: (d) => AlertDialog(
          title: Text('Start this mission?'),
          content: Text(
            'It builds on ${missing.map((m) => '"${m['title']}"${m['panel'] != skill['panel'] ? ' (${panelLabels[m['panel']]})' : ''}').join(' and ')}, '
            'which you have not finished yet. You can still start it now.',
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(d, false), child: Text('Not now')),
            FilledButton(onPressed: () => Navigator.pop(d, true), child: Text('Start anyway')),
          ],
        ),
      );
      if (go != true || !context.mounted) return;
    }
    await context.push('/skill/$id');
    s.loadSkills(); // progress may have changed
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final state = s.skillState(skill);
    final prog = s.skillProgress(skill);
    final locked = state == 'locked', done = state == 'done';
    final total = s.skillTotal(skill), answered = s.skillAnswered(skill);
    return Semantics(
      button: true,
      label: '${skill['title']}. ${done ? 'Done' : locked ? 'Not unlocked yet, can still be started' : '$answered of $total questions answered'}',
      excludeSemantics: true,
      child: GestureDetector(
        onTap: () => _open(context),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          SizedBox(
            width: 60, height: 60,
            child: Stack(alignment: Alignment.center, children: [
              Positioned.fill(
                child: TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0, end: prog),
                  duration: Duration(milliseconds: 600),
                  curve: Curves.easeOutCubic,
                  builder: (_, v, __) => CircularProgressIndicator(value: v, strokeWidth: 5, color: kGreen, backgroundColor: kSurface),
                ),
              ),
              Container(
                width: 46, height: 46,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: done ? kPrimary : locked ? kLine : kSurface,
                  border: Border.all(color: locked ? kBorder : kPrimary, width: 2),
                  boxShadow: locked ? null : [BoxShadow(color: kPrimary.withValues(alpha: 0.25), blurRadius: 8, offset: Offset(0, 3))],
                ),
                child: Icon(done ? Icons.check : locked ? Icons.lock_outline : Icons.play_arrow_rounded,
                    color: done ? Colors.white : locked ? kFaint : kPrimaryText, size: 24),
              ),
            ]),
          ),
          SizedBox(height: 4),
          Container(
            padding: EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(color: kBg.withValues(alpha: 0.85), borderRadius: BorderRadius.circular(6)),
            child: Column(children: [
              Text(skill['title'] as String, maxLines: 2, overflow: TextOverflow.ellipsis, textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: locked ? kMuted : kInk, height: 1.2)),
              Text(done ? 'Done' : total == 0 ? 'New' : '$answered/$total', style: TextStyle(fontSize: 10.5, color: kMuted)),
            ]),
          ),
        ]),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// The spinnable wheel of panels. rot is the rotation in radians; slice i sits
// at screen angle -pi/2 + rot + i*step, so the selected slice is the one under
// the pointer: index = round(-rot / step).

class _SpinWheel extends StatefulWidget {
  final List<String> panels;
  final bool left; // wide web: the wheel sits on the left edge, pointer facing right
  _SpinWheel({super.key, required this.panels, this.left = false});
  @override
  State<_SpinWheel> createState() => _SpinWheelState();
}

class _SpinWheelState extends State<_SpinWheel> with SingleTickerProviderStateMixin {
  late final AnimationController _rot = AnimationController.unbounded(vsync: this);
  Offset _centre = Offset.zero;
  double _radius = 1;
  int _sel = -1;

  int get n => widget.panels.length;
  double get step => 2 * math.pi / n;
  int _indexFor(double r) => ((-r / step).round() % n + n) % n;

  @override
  void initState() {
    super.initState();
    final s = context.read<AppState>();
    final i = widget.panels.indexOf(s.selectedPanel);
    _rot.value = -math.max(i, 0) * step;
    _sel = _indexFor(_rot.value);
    _rot.addListener(_onTurn);
    // Fonts download after the first paint; when they arrive, drop the cached
    // letter layouts (made with the fallback font) and repaint.
    for (final w in [FontWeight.w600, FontWeight.w700]) {
      _lora(fontWeight: w);
    }
    GoogleFonts.pendingFonts().then((_) {
      _WheelPainter._letters.clear();
      if (mounted) setState(() {});
    });
    if (!s.wheelSpun && !s.wheelNudged) {
      s.wheelNudged = true;
      _nudge();
    }
  }

  @override
  void dispose() {
    _rot.dispose();
    super.dispose();
  }

  Future<void> _nudge() async {
    await Future.delayed(Duration(milliseconds: 700));
    for (final d in [0.16, -0.12, 0.0]) {
      if (!mounted || context.read<AppState>().wheelSpun) return;
      await _rot.animateTo(-_sel * step + d, duration: Duration(milliseconds: 420), curve: Curves.easeInOut);
    }
  }

  void _onTurn() {
    final i = _indexFor(_rot.value);
    if (i != _sel) {
      _sel = i;
      HapticFeedback.selectionClick();
      Sfx.tick();
      context.read<AppState>().selectPanel(widget.panels[i]);
    }
    setState(() {});
  }

  void _snapTo(double target, {int? ms}) {
    final k = (-target / step).round();
    final end = -k * step;
    final dist = (end - _rot.value).abs();
    _rot.animateTo(end, duration: Duration(milliseconds: ms ?? (260 + dist * 380).clamp(260, 1500).round()), curve: Curves.easeOutCubic);
  }

  double _angle(Offset p) => math.atan2(p.dy - _centre.dy, p.dx - _centre.dx);

  void _tap(TapUpDetails d) {
    final dist = (d.localPosition - _centre).distance;
    if (dist < _radius * 0.4) {
      final turns = 2 * math.pi * (1 + math.Random().nextDouble());
      _snapTo(_rot.value - turns, ms: 1600);
      return;
    }
    if (dist > _radius) return;
    // Angle from the pointer, in the wheel's own frame (the left wheel is turned 90 degrees).
    final a = _angle(d.localPosition) + (widget.left ? 0 : math.pi / 2) - _rot.value;
    final i = ((a / step).round() % n + n) % n;
    var diff = (-i * step - _rot.value) % (2 * math.pi);
    if (diff > math.pi) diff -= 2 * math.pi;
    _snapTo(_rot.value + diff);
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    return LayoutBuilder(builder: (context, c) {
      final w = c.maxWidth, h = c.maxHeight;
      final left = widget.left;
      if (left) {
        _radius = math.min(h * 0.46, w - 30);
        _centre = Offset(-_radius * 0.04, h / 2);
      } else {
        _radius = math.min(w * 0.6, (h - 18) / 0.98);
        _centre = Offset(w / 2, h + _radius * 0.02);
      }
      // Sideways swipe on the bottom wheel; up and down on the left wheel.
      void dragUpdate(double d) => _rot.value += d / (_radius * 0.9);
      void dragEnd(double v) => _snapTo(_rot.value + ((v / (_radius * 0.9)) * 0.35).clamp(-2 * math.pi, 2 * math.pi));
      return Stack(clipBehavior: Clip.none, children: [
        Positioned.fill(
          child: Semantics(
            label: 'Topic wheel. Selected: ${panelLabels[widget.panels[_sel]]}. Swipe sideways to spin, or use the arrow buttons.',
            child: GestureDetector(
              behavior: HitTestBehavior.opaque,
              onHorizontalDragStart: left ? null : (_) => _rot.stop(),
              onHorizontalDragUpdate: left ? null : (d) => dragUpdate(d.delta.dx),
              onHorizontalDragEnd: left ? null : (d) => dragEnd(d.velocity.pixelsPerSecond.dx),
              onVerticalDragStart: left ? (_) => _rot.stop() : null,
              onVerticalDragUpdate: left ? (d) => dragUpdate(d.delta.dy) : null,
              onVerticalDragEnd: left ? (d) => dragEnd(d.velocity.pixelsPerSecond.dy) : null,
              onTapUp: _tap,
              child: MouseRegion(
                cursor: SystemMouseCursors.grab,
                child: CustomPaint(painter: _WheelPainter(widget.panels, s, _rot.value, _centre, _radius, _sel, left: left)),
              ),
            ),
          ),
        ),
        Positioned(left: 8, top: left ? 12 : 4, child: _SpinButton(icon: Icons.rotate_left, tip: 'Previous topic', onTap: () => _snapTo(_rot.value + step))),
        Positioned(
          right: left ? null : 8, left: left ? 8 : null, top: left ? null : 4, bottom: left ? 12 : null,
          child: _SpinButton(icon: Icons.rotate_right, tip: 'Next topic', onTap: () => _snapTo(_rot.value - step)),
        ),
        Positioned(
          left: 0, right: 0, top: 0,
          child: IgnorePointer(
            child: AnimatedOpacity(
              opacity: s.wheelSpun ? 0 : 1,
              duration: Duration(milliseconds: 400),
              child: Center(
                child: Container(
                  padding: EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(color: kPrimary, borderRadius: BorderRadius.circular(999)),
                  child: Row(mainAxisSize: MainAxisSize.min, children: [
                    Icon(Icons.swipe, size: 16, color: Colors.white),
                    SizedBox(width: 6),
                    Text(left ? 'Swipe to spin' : 'Swipe to spin', style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w700)),
                  ]),
                ),
              ),
            ),
          ),
        ),
      ]);
    });
  }
}

class _SpinButton extends StatelessWidget {
  final IconData icon;
  final String tip;
  final VoidCallback onTap;
  _SpinButton({required this.icon, required this.tip, required this.onTap});
  @override
  Widget build(BuildContext context) => Material(
        color: kSurface,
        shape: CircleBorder(side: BorderSide(color: kWheelRim, width: 2)),
        child: IconButton(tooltip: tip, icon: Icon(icon, color: kPrimaryText), onPressed: onTap),
      );
}

class _WheelPainter extends CustomPainter {
  final List<String> panels;
  final AppState s;
  final double rot;
  final Offset c;
  final double r;
  final int sel;
  final bool left;
  _WheelPainter(this.panels, this.s, this.rot, this.c, this.r, this.sel, {this.left = false});

  // Laid-out letters are cached: the wheel repaints every animation frame, and
  // laying out each curved letter again (plus a font lookup) made frames slow.
  static final Map<String, (List<TextPainter>, double)> _letters = {};

  (List<TextPainter>, double) _layout(String text, TextStyle style, double maxArc) {
    final key = '$text|${style.fontSize?.toStringAsFixed(1)}|${style.color?.toARGB32()}|${style.fontWeight}|${maxArc.round()}';
    return _letters[key] ??= () {
      if (_letters.length > 400) _letters.clear();
      var tps = [for (final ch in text.characters) TextPainter(text: TextSpan(text: ch, style: style), textDirection: TextDirection.ltr)..layout()];
      var total = tps.fold<double>(0, (a, t) => a + t.width);
      if (total > maxArc && style.fontSize != null) {
        final f = style.fontSize! * maxArc / total;
        tps = [for (final ch in text.characters) TextPainter(text: TextSpan(text: ch, style: style.copyWith(fontSize: f)), textDirection: TextDirection.ltr)..layout()];
        total = tps.fold<double>(0, (a, t) => a + t.width);
      }
      return (tps, total);
    }();
  }

  void _arcText(Canvas canvas, double radius, double mid, String text, TextStyle style, double maxArc) {
    final (tps, total) = _layout(text, style, maxArc);
    var a = mid - total / radius / 2;
    for (final tp in tps) {
      final half = tp.width / 2 / radius;
      a += half;
      canvas.save();
      canvas.translate(c.dx + math.cos(a) * radius, c.dy + math.sin(a) * radius);
      canvas.rotate(a + math.pi / 2);
      tp.paint(canvas, Offset(-tp.width / 2, -tp.height / 2));
      canvas.restore();
      a += half;
    }
  }

  @override
  void paint(Canvas canvas, Size size) {
    final n = panels.length, step = 2 * math.pi / n;
    final rim = r * 0.12, hub = r * 0.4, face = r - rim;
    if (left) {
      // Same drawing as the bottom wheel, turned so the top faces right.
      canvas.save();
      canvas.translate(c.dx, c.dy);
      canvas.rotate(math.pi / 2);
      canvas.translate(-c.dx, -c.dy);
    }
    for (var i = 0; i < n; i++) {
      final a0 = -math.pi / 2 + rot + i * step - step / 2;
      final path = Path()
        ..arcTo(Rect.fromCircle(center: c, radius: face), a0, step, true)
        ..arcTo(Rect.fromCircle(center: c, radius: hub), a0 + step, -step, false)
        ..close();
      canvas.drawPath(path, Paint()..color = i == sel ? kWheelFaceSel : kWheelFace);
      final dir = Offset(math.cos(a0), math.sin(a0));
      canvas.drawLine(c + dir * hub, c + dir * face, Paint()..color = kWheelLine..strokeWidth = 2);
    }
    canvas.drawCircle(c, r - rim / 2, Paint()..color = kWheelRim..style = PaintingStyle.stroke..strokeWidth = rim);

    final start = s.startPanel;
    for (var i = 0; i < n; i++) {
      final mid = -math.pi / 2 + rot + i * step;
      final norm = math.atan2(math.sin(mid), math.cos(mid));
      // Only label slices near the top; the side ones are cut off by the screen edge.
      if ((norm + math.pi / 2).abs() > 1.15 && (norm + math.pi / 2).abs() < 2 * math.pi - 1.15) continue;
      final p = panels[i];
      final isSel = i == sel;
      _arcText(
        canvas, r - rim / 2, mid, (panelLabels[p] ?? p).toUpperCase(),
        _lora(fontSize: rim * (isSel ? 0.68 : 0.5), fontWeight: FontWeight.w700, color: isSel ? kRimLabelSel : kRimLabel, letterSpacing: 0.5),
        step * (r - rim / 2) * 0.9,
      );
      final prog = s.panelProgress(p);
      final span = math.min(step * 0.7, 1.2);
      final ring = Rect.fromCircle(center: c, radius: face - r * 0.035);
      canvas.drawArc(ring, mid - span / 2, span, false,
          Paint()..color = kWheelLine.withValues(alpha: 0.55)..style = PaintingStyle.stroke..strokeWidth = r * 0.03..strokeCap = StrokeCap.round);
      if (prog > 0) {
        canvas.drawArc(ring, mid - span / 2, span * prog, false,
            Paint()..color = kHub..style = PaintingStyle.stroke..strokeWidth = r * 0.03..strokeCap = StrokeCap.round);
      }
      final ks = s.skillsIn(p);
      final doneN = ks.where(s.skillDone).length;
      final faceStyle = _lora(fontSize: r * (isSel ? 0.055 : 0.046), fontWeight: FontWeight.w600, color: kFaceLabel);
      final faceArc = math.min(step, 1.4) * (face - r * 0.12) * 0.9;
      _arcText(canvas, face - r * 0.11, mid, ks.isEmpty ? 'COMING SOON' : isSel ? '$doneN/${ks.length} MISSIONS DONE' : '${ks.length} MISSIONS', faceStyle, faceArc);
      if (p == start) {
        _arcText(canvas, face - r * 0.2, mid, 'START', faceStyle.copyWith(fontSize: r * (isSel ? 0.075 : 0.055), fontWeight: FontWeight.w700), faceArc);
      }
    }

    // Hub: a crocodile head peeking up, with the spin cue.
    canvas.drawCircle(c, hub, Paint()..color = kHub);
    canvas.drawCircle(c, hub - 3, Paint()..color = kHubRim..style = PaintingStyle.stroke..strokeWidth = 6);
    paintCrocoEyes(canvas, Offset(c.dx, c.dy - hub + hub * 0.12), hub * 0.95, kHub);
    for (final dx in [-hub * 0.09, hub * 0.09]) {
      canvas.drawOval(Rect.fromCenter(center: Offset(c.dx + dx, c.dy - hub * 0.2), width: hub * 0.06, height: hub * 0.035), Paint()..color = kHubRim);
    }
    final top = Offset(c.dx, c.dy - r - 4);
    final tri = Path()
      ..moveTo(top.dx - 11, top.dy - 12)
      ..lineTo(top.dx + 11, top.dy - 12)
      ..lineTo(top.dx, top.dy + 4)
      ..close();
    canvas.drawPath(tri, Paint()..color = kPrimary);
    canvas.drawPath(tri, Paint()..color = Colors.white..style = PaintingStyle.stroke..strokeWidth = 2);
    if (left) canvas.restore();
    final spin = TextPainter(
      text: TextSpan(text: 'SPIN', style: _lora(fontSize: r * 0.075, fontWeight: FontWeight.w700, color: Colors.white, letterSpacing: 1.5)),
      textDirection: TextDirection.ltr,
    )..layout();
    // Upright on both wheels: above the centre on the bottom wheel, right of it on the left wheel.
    final at = left ? Offset(c.dx + hub * 0.5, c.dy) : Offset(c.dx, c.dy - hub * 0.46);
    spin.paint(canvas, at - Offset(spin.width / 2, spin.height / 2));

  }

  @override
  bool shouldRepaint(covariant _WheelPainter old) => true;
}

// ---------------------------------------------------------------------------
// List view alternative to the wheel (inclusive mode).

class _PanelPicker extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    return Container(
      color: kSurface.withValues(alpha: 0.9),
      padding: EdgeInsets.only(top: 10),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Padding(padding: EdgeInsets.only(left: 20), child: Text('Topics', style: TextStyle(fontWeight: FontWeight.w700))),
        SizedBox(height: 8),
        SizedBox(
          height: 84,
          child: ListView(scrollDirection: Axis.horizontal, padding: EdgeInsets.symmetric(horizontal: 16), children: [
            for (final p in s.panels)
              Padding(
                padding: EdgeInsets.only(right: 8),
                child: ChoiceChip(
                  selected: p == s.selectedPanel,
                  onSelected: (_) => s.selectPanel(p),
                  label: Column(mainAxisSize: MainAxisSize.min, children: [
                    Text(panelLabels[p] ?? p),
                    Text('${(s.panelProgress(p) * 100).round()}% done', style: TextStyle(fontSize: 11, color: kMuted)),
                  ]),
                ),
              ),
          ]),
        ),
      ]),
    );
  }
}

// ---------------------------------------------------------------------------
// Daily question (idea from Basis): one question a day for bonus Scales. The
// dialog has a heading, shows the right answer and its explanation, and closes.

void showDailyQuestion(BuildContext context) {
  final s = context.read<AppState>();
  final rm = s.roadmap;
  if (rm == null) return;
  final q = rm.slice('money_market').nodes[1].questions[1];
  int? picked;
  showDialog(
    context: context,
    builder: (ctx) => StatefulBuilder(
      builder: (ctx, setD) => AlertDialog(
        title: Row(children: [
          Icon(Icons.today, color: kWarnIcon),
          SizedBox(width: 8),
          Expanded(child: Text("Today's question")),
          IconButton(tooltip: 'Close', icon: Icon(Icons.close), onPressed: () => Navigator.pop(ctx)),
        ]),
        content: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Text(q.q, style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: kInk)),
            SizedBox(height: 12),
            for (final (i, o) in q.options.indexed)
              Padding(
                padding: EdgeInsets.only(bottom: 8),
                child: OutlinedButton(
                  style: OutlinedButton.styleFrom(
                    alignment: Alignment.centerLeft,
                    padding: EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                    backgroundColor: picked == null ? null : i == q.answer ? kGreenSoft : i == picked ? kRedSoft : null,
                    side: BorderSide(color: picked == null ? kBorder : i == q.answer ? kGreen : i == picked ? kRed : kBorder, width: picked == null ? 1 : 2),
                  ),
                  onPressed: picked != null
                      ? null
                      : () {
                          setD(() => picked = i);
                          i == q.answer ? Sfx.correct() : Sfx.wrong();
                          s.answerDaily(i == q.answer);
                        },
                  child: Row(children: [
                    Expanded(child: Text(o, style: TextStyle(color: kInk))),
                    if (picked != null && i == q.answer) Icon(Icons.check, color: kGreen),
                    if (picked != null && i == picked && i != q.answer) Icon(Icons.close, color: kRed),
                  ]),
                ),
              ),
            if (picked != null) ...[
              SizedBox(height: 4),
              Text(picked == q.answer ? 'Correct! +${Rewards.dailyRight} Scales' : 'Not quite. +${Rewards.dailyTried} Scales for trying',
                  style: TextStyle(fontWeight: FontWeight.w800, color: picked == q.answer ? kGreen : kWarnText)),
              SizedBox(height: 6),
              Text('Answer: ${q.options[q.answer!]}. ${q.why ?? ''}', style: TextStyle(color: kBody, height: 1.4)),
            ],
          ]),
        ),
        actions: [if (picked != null) FilledButton(onPressed: () => Navigator.pop(ctx), child: Text('Close'))],
      ),
    ),
  );
}


/// The planned missions of a panel without content yet, drawn in the "coming later" colour.
/// Tapping one opens the coming-later screen.
class _Planned extends StatelessWidget {
  final String panel;
  final bool horizontal;
  _Planned({super.key, required this.panel, this.horizontal = false});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final nodes = [...s.plannedIn(panel)]..sort((a, b) => '${a['level']}${a['id']}'.compareTo('${b['level']}${b['id']}'));
    final items = <Widget>[];
    for (final (i, n) in nodes.indexed) {
      if (i > 0) items.add(horizontal ? _dash(48, 3) : _dash(3, 28));
      items.add(_PlannedNode(node: n));
    }
    return Padding(
      padding: EdgeInsets.fromLTRB(24, 24, 24, 24),
      child: horizontal
          ? Row(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.center, children: [_dash(40, 3), ...items])
          : Column(mainAxisSize: MainAxisSize.min, children: [...items.reversed, _dash(3, 28)]),
    );
  }

  Widget _dash(double w, double h) => Container(
        width: w, height: h,
        decoration: BoxDecoration(color: kWarnBorder, borderRadius: BorderRadius.circular(2)),
      );
}

class _PlannedNode extends StatelessWidget {
  final Map<String, dynamic> node;
  _PlannedNode({required this.node});

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        label: '${node['title']}, coming later',
        excludeSemantics: true,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: () => GoRouter.of(context).push('/coming-later?node=${node['id']}'),
          child: SizedBox(
            width: 130,
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Container(
                width: 60, height: 60,
                decoration: BoxDecoration(color: kWarnSoft, shape: BoxShape.circle, border: Border.all(color: kWarnIcon, width: 2.5)),
                child: Icon(Icons.schedule, color: kWarnIcon),
              ),
              SizedBox(height: 6),
              Text('${node['title']}', textAlign: TextAlign.center, maxLines: 2, overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: kInk, height: 1.2)),
              Text('Coming later', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: kWarnText)),
            ]),
          ),
        ),
      );
}

/// Planned missions of a panel that already has some: small chips in the coming-later colour.
class _PlannedStrip extends StatelessWidget {
  final String panel;
  _PlannedStrip({required this.panel});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    return Wrap(spacing: 6, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [
      Text('Coming later:', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: kWarnText)),
      for (final n in s.plannedIn(panel))
        ActionChip(
          avatar: Icon(Icons.schedule, size: 16, color: kWarnIcon),
          label: Text('${n['title']}', style: TextStyle(fontSize: 12, color: kInk)),
          backgroundColor: kWarnSoft,
          side: BorderSide(color: kWarnBorder),
          visualDensity: VisualDensity.compact,
          onPressed: () => GoRouter.of(context).push('/coming-later?node=${n['id']}'),
        ),
    ]);
  }
}
