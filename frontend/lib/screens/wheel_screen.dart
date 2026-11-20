// Home (layout from the Figma frames in docs/design/): the user's header on
// top, the roadmap of the selected topic in the middle, and a spinnable wheel
// of the 13 investment types at the bottom. Drag or flick the wheel, tap a
// slice, tap the hub for a random spin, or use the arrow buttons. The slice
// under the pointer at the top is the selected topic. Every slice shows its
// risk and progress; every mission on the roadmap shows its own progress.
// List view (Profile > Accessibility) replaces the wheel with simple chips.

import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../models/content.dart';
import '../widgets/common.dart';

/// Short names that fit on the wheel's rim.
const _short = {
  'bonds': 'Bonds',
  'mutual_and_index_funds': 'Funds',
  'etfs': 'ETFs',
  'real_estate': 'Real estate',
  'money_market': 'Money market',
  'guaranteed_products': 'Guaranteed',
  'options': 'Options',
  'futures': 'Futures',
  'currencies': 'Currencies',
  'precious_metals': 'Metals',
  'variable_life_annuities': 'Annuities',
  'dpp_limited_partnerships': 'Partnerships',
  'stocks': 'Stocks',
};

class WheelScreen extends StatelessWidget {
  WheelScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final rm = s.roadmap;
    if (rm == null) return Scaffold(body: Center(child: CircularProgressIndicator()));
    final sel = rm.slice(s.selectedSlice);
    return Scaffold(
      backgroundColor: kBg,
      appBar: StatsBar(),
      body: LayoutBuilder(builder: (context, c) {
        final w = c.maxWidth;
        final wheelH = s.listView ? 132.0 : math.min(w * 0.66, c.maxHeight * 0.5);
        // The roadmap and the wheel scroll together. reverse: true starts at
        // the bottom, so the wheel and the first missions show first.
        return SingleChildScrollView(
          reverse: true,
          child: ConstrainedBox(
            constraints: BoxConstraints(minHeight: c.maxHeight),
            child: Column(mainAxisAlignment: MainAxisAlignment.end, children: [
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
                  child: _Roadmap(key: ValueKey(sel.key), slice: sel),
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
                child: s.listView ? _SlicePicker(slices: rm.slices) : _SpinWheel(slices: rm.slices),
              ),
            ]),
          ),
        );
      }),
    );
  }
}

// ---------------------------------------------------------------------------
// Roadmap of the selected topic, drawn as branching paths that grow upwards
// out of the wheel. A mission's depth is its longest chain of prerequisites.

class _Roadmap extends StatelessWidget {
  final Slice slice;
  _Roadmap({super.key, required this.slice});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final prog = s.sliceProgress(slice);
    final done = slice.nodes.where((n) => s.doneNodes.contains(n.id)).length;
    final focus = s.focusSlices.contains(slice.key);
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Padding(
        padding: EdgeInsets.fromLTRB(20, 4, 16, 0),
        child: Row(children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(slice.label, maxLines: 2, overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.lora(fontSize: 22, fontWeight: FontWeight.w700, color: kInk, height: 1.15)),
              SizedBox(height: 2),
              Text('${riskName(slice.risk)} ride · $done of ${slice.nodes.length} missions done${focus ? ' · your focus' : ''}',
                  style: TextStyle(fontSize: 12.5, color: kMuted)),
            ]),
          ),
          SizedBox(width: 8),
          Semantics(
            label: '${(prog * 100).round()} percent of ${slice.label} done',
            excludeSemantics: true,
            child: SizedBox(
              width: 48, height: 48,
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
              onPressed: () => _openDaily(context, s),
            ),
          IconButton(
            tooltip: 'Open the full roadmap',
            icon: Icon(Icons.open_in_full, color: kPrimaryText),
            onPressed: () => context.push('/slice/${slice.key}'),
          ),
        ]),
      ),
      _Tree(slice: slice),
    ]);
  }
}

class _Tree extends StatelessWidget {
  final Slice slice;
  _Tree({required this.slice});

  static const rowH = 104.0, pad = 40.0;

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    // Depth = longest chain of prerequisites (roots at depth 0, at the bottom).
    final byId = {for (final n in slice.nodes) n.id: n};
    final depth = <String, int>{};
    int d(Node n) => depth[n.id] ??= n.after.isEmpty ? 0 : 1 + n.after.where(byId.containsKey).map((a) => d(byId[a]!)).fold(0, math.max);
    for (final n in slice.nodes) {
      d(n);
    }
    final rows = <int, List<Node>>{};
    for (final n in slice.nodes) {
      rows.putIfAbsent(depth[n.id]!, () => []).add(n);
    }
    final maxDepth = rows.keys.fold(0, math.max);

    final h = pad * 2 + maxDepth * rowH + 64;
    return LayoutBuilder(builder: (context, c) {
      final w = c.maxWidth;
      final pos = <String, Offset>{};
      for (final MapEntry(key: r, value: list) in rows.entries) {
        for (final (k, n) in list.indexed) {
          final x = list.length == 1
              ? w * (r.isEven ? 0.38 : 0.62) // single missions zigzag like a trail
              : w * (k + 1) / (list.length + 1);
          pos[n.id] = Offset(x, h - pad - 24 - r * rowH);
        }
      }
      return SizedBox(
        width: w,
        height: h,
        child: Stack(clipBehavior: Clip.none, children: [
          Positioned.fill(child: CustomPaint(painter: _PathsPainter(slice, pos, s, Offset(w / 2, h + 8)))),
          for (final n in slice.nodes)
            Positioned(
              left: pos[n.id]!.dx - 52,
              top: pos[n.id]!.dy - 30,
              width: 104,
              child: _MissionNode(slice: slice, node: n),
            ),
        ]),
      );
    });
  }
}

class _PathsPainter extends CustomPainter {
  final Slice slice;
  final Map<String, Offset> pos;
  final AppState s;
  final Offset root;
  _PathsPainter(this.slice, this.pos, this.s, this.root);

  void _trail(Canvas canvas, Offset a, Offset b, bool walked) {
    final dy = (a.dy - b.dy).abs() * 0.55;
    final path = Path()
      ..moveTo(a.dx, a.dy)
      ..cubicTo(a.dx, a.dy - dy, b.dx, b.dy + dy, b.dx, b.dy);
    canvas.drawPath(path, Paint()..color = (walked ? kWheelRim : kLine)..style = PaintingStyle.stroke..strokeWidth = 14..strokeCap = StrokeCap.round);
    // Dashed centre line makes it read as a path.
    final dash = Paint()..color = walked ? Colors.white.withValues(alpha: 0.85) : kBorder..style = PaintingStyle.stroke..strokeWidth = 2.5..strokeCap = StrokeCap.round;
    for (final m in path.computeMetrics()) {
      for (double t = 0; t < m.length; t += 12) {
        canvas.drawPath(m.extractPath(t, math.min(t + 5, m.length)), dash);
      }
    }
  }

  @override
  void paint(Canvas canvas, Size size) {
    for (final n in slice.nodes) {
      final p = pos[n.id]!;
      if (n.after.isEmpty) {
        _trail(canvas, root, p, true); // the trunk grows out of the wheel
      }
      for (final a in n.after) {
        final q = pos[a];
        if (q != null) _trail(canvas, q, p, s.doneNodes.contains(a));
      }
    }
  }

  @override
  bool shouldRepaint(covariant _PathsPainter old) => true;
}

class _MissionNode extends StatelessWidget {
  final Slice slice;
  final Node node;
  _MissionNode({required this.slice, required this.node});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final state = s.nodeState(node);
    final prog = s.nodeProgress(node);
    final locked = state == 'locked', done = state == 'done';
    final answered = done ? node.questions.length : (s.nodeAnswered[node.id] ?? 0);
    final lockReason = node.after.isEmpty
        ? null
        : 'Finish ${node.after.map((a) => slice.nodes.firstWhere((x) => x.id == a).title).join(' and ')} first';
    return Semantics(
      button: true,
      label: '${node.title}. ${done ? 'Done' : locked ? (lockReason ?? 'Locked') : '$answered of ${node.questions.length} questions answered'}',
      excludeSemantics: true,
      child: GestureDetector(
        onTap: locked
            ? () => ScaffoldMessenger.of(context)
              ..hideCurrentSnackBar()
              ..showSnackBar(SnackBar(content: Text(lockReason ?? 'Locked')))
            : () => context.push('/mission/${slice.key}/${Uri.encodeComponent(node.id)}'),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          SizedBox(
            width: 60, height: 60,
            child: Stack(alignment: Alignment.center, children: [
              // The mission's own progress ring.
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
                child: Icon(done ? Icons.check : locked ? Icons.lock : Icons.play_arrow_rounded,
                    color: done ? Colors.white : locked ? kFaint : kPrimaryText, size: 24),
              ),
            ]),
          ),
          SizedBox(height: 4),
          Container(
            padding: EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(color: kBg.withValues(alpha: 0.85), borderRadius: BorderRadius.circular(6)),
            child: Column(children: [
              Text(node.title, maxLines: 2, overflow: TextOverflow.ellipsis, textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: locked ? kMuted : kInk, height: 1.2)),
              Text(done ? 'Done' : locked ? 'Locked' : '$answered/${node.questions.length}',
                  style: TextStyle(fontSize: 10.5, color: kMuted)),
            ]),
          ),
        ]),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// The spinnable wheel. rot is the wheel's rotation in radians; slice i sits at
// screen angle -pi/2 + rot + i*step (clockwise, 0 = right), so the selected
// slice is the one nearest the top: index = round(-rot / step).

class _SpinWheel extends StatefulWidget {
  final List<Slice> slices;
  _SpinWheel({required this.slices});
  @override
  State<_SpinWheel> createState() => _SpinWheelState();
}

class _SpinWheelState extends State<_SpinWheel> with SingleTickerProviderStateMixin {
  late final AnimationController _rot = AnimationController.unbounded(vsync: this);
  Offset? _last;
  Offset _centre = Offset.zero;
  double _radius = 1;
  int _sel = -1;

  int get n => widget.slices.length;
  double get step => 2 * math.pi / n;
  int _indexFor(double r) => ((-r / step).round() % n + n) % n;

  @override
  void initState() {
    super.initState();
    final s = context.read<AppState>();
    final i = widget.slices.indexWhere((x) => x.key == s.selectedSlice);
    _rot.value = -math.max(i, 0) * step;
    _sel = _indexFor(_rot.value);
    _rot.addListener(_onTurn);
    if (!s.wheelSpun) _nudge();
  }

  @override
  void dispose() {
    _rot.dispose();
    super.dispose();
  }

  // A small wiggle on first visit, so it is obvious the wheel moves.
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
      context.read<AppState>().selectSlice(widget.slices[i].key, bySpin: true);
    }
    setState(() {});
  }

  void _snapTo(double target, {int? ms}) {
    final k = (-target / step).round();
    final end = -k * step;
    final dist = (end - _rot.value).abs();
    _rot.animateTo(end,
        duration: Duration(milliseconds: ms ?? (260 + dist * 380).clamp(260, 1500).round()), curve: Curves.easeOutCubic);
  }

  double _angle(Offset p) => math.atan2(p.dy - _centre.dy, p.dx - _centre.dx);

  void _panStart(DragStartDetails d) {
    _rot.stop();
    _last = d.localPosition;
  }

  // Swiping right turns the top of the wheel to the right (clockwise).
  void _panUpdate(DragUpdateDetails d) {
    _rot.value += d.delta.dx / (_radius * 0.9);
    _last = d.localPosition;
  }

  void _panEnd(DragEndDetails d) {
    final omega = d.velocity.pixelsPerSecond.dx / (_radius * 0.9); // radians per second
    final throwBy = (omega * 0.35).clamp(-2 * math.pi, 2 * math.pi);
    _last = null;
    _snapTo(_rot.value + throwBy);
  }

  void _tap(TapUpDetails d) {
    final dist = (d.localPosition - _centre).distance;
    if (dist < _radius * 0.4) {
      // Hub: a random spin of one to two turns.
      final turns = 2 * math.pi * (1 + math.Random().nextDouble());
      _snapTo(_rot.value - turns, ms: 1600);
      return;
    }
    if (dist > _radius) return;
    final a = _angle(d.localPosition) + math.pi / 2 - _rot.value; // angle from the top, wheel frame
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
      _radius = math.min(w * 0.6, (h - 18) / 0.98);
      _centre = Offset(w / 2, h + _radius * 0.02);
      return Stack(clipBehavior: Clip.none, children: [
        Positioned.fill(
          child: Semantics(
            label: 'Topic wheel. Selected: ${widget.slices[_sel].label}. Swipe sideways to spin, or use the arrow buttons.',
            child: GestureDetector(
              behavior: HitTestBehavior.opaque,
              onHorizontalDragStart: _panStart,
              onHorizontalDragUpdate: _panUpdate,
              onHorizontalDragEnd: _panEnd,
              onTapUp: _tap,
              child: MouseRegion(
                cursor: SystemMouseCursors.grab,
                child: CustomPaint(painter: _WheelPainter(widget.slices, s, _rot.value, _centre, _radius, _sel)),
              ),
            ),
          ),
        ),
        // Arrow buttons: an obvious "this turns" cue, and keyboard / screen-reader friendly.
        Positioned(
          left: 8, top: 4,
          child: _SpinButton(icon: Icons.rotate_left, tip: 'Previous topic', onTap: () => _snapTo(_rot.value + step)),
        ),
        Positioned(
          right: 8, top: 4,
          child: _SpinButton(icon: Icons.rotate_right, tip: 'Next topic', onTap: () => _snapTo(_rot.value - step)),
        ),
        // "Spin me" hint until the first spin.
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
                    Text('Swipe to spin', style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w700)),
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
  final List<Slice> slices;
  final AppState s;
  final double rot;
  final Offset c;
  final double r;
  final int sel;
  _WheelPainter(this.slices, this.s, this.rot, this.c, this.r, this.sel);

  /// Text laid out along an arc, centred on angle [mid], reading clockwise.
  void _arcText(Canvas canvas, double radius, double mid, String text, TextStyle style, double maxArc) {
    var tps = [for (final ch in text.characters) TextPainter(text: TextSpan(text: ch, style: style), textDirection: TextDirection.ltr)..layout()];
    var total = tps.fold<double>(0, (a, t) => a + t.width);
    if (total > maxArc && style.fontSize != null) {
      final f = style.fontSize! * maxArc / total;
      tps = [for (final ch in text.characters) TextPainter(text: TextSpan(text: ch, style: style.copyWith(fontSize: f)), textDirection: TextDirection.ltr)..layout()];
      total = tps.fold<double>(0, (a, t) => a + t.width);
    }
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
    final n = slices.length, step = 2 * math.pi / n;
    final rim = r * 0.12, hub = r * 0.4, face = r - rim;

    // Faces.
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
    // Rim band.
    canvas.drawCircle(c, r - rim / 2, Paint()..color = kWheelRim..style = PaintingStyle.stroke..strokeWidth = rim);

    // Labels and progress, only for slices in the visible top half.
    for (var i = 0; i < n; i++) {
      final mid = -math.pi / 2 + rot + i * step;
      final norm = math.atan2(math.sin(mid), math.cos(mid)); // -pi..pi
      if (norm > 0.35 && norm < math.pi - 0.35) continue; // bottom half is hidden
      final sl = slices[i];
      final isSel = i == sel;
      final arc = step * (r - rim / 2) * 0.92;
      _arcText(
        canvas, r - rim / 2, mid, (_short[sl.key] ?? sl.label).toUpperCase(),
        GoogleFonts.lora(fontSize: rim * (isSel ? 0.68 : 0.5), fontWeight: FontWeight.w700, color: isSel ? kRimLabelSel : kRimLabel, letterSpacing: 0.5),
        arc,
      );
      // Progress arc just inside the rim.
      final prog = s.sliceProgress(sl);
      final span = step * 0.7;
      final ring = Rect.fromCircle(center: c, radius: face - r * 0.035);
      canvas.drawArc(ring, mid - span / 2, span, false,
          Paint()..color = kWheelLine.withValues(alpha: 0.55)..style = PaintingStyle.stroke..strokeWidth = r * 0.03..strokeCap = StrokeCap.round);
      if (prog > 0) {
        canvas.drawArc(ring, mid - span / 2, span * prog, false,
            Paint()..color = kHub..style = PaintingStyle.stroke..strokeWidth = r * 0.03..strokeCap = StrokeCap.round);
      }
      final faceStyle = GoogleFonts.lora(fontSize: r * 0.052, fontWeight: FontWeight.w600, color: kFaceLabel);
      final faceArc = step * (face - r * 0.12) * 0.9;
      final doneN = sl.nodes.where((x) => s.doneNodes.contains(x.id)).length;
      if (isSel) {
        _arcText(canvas, face - r * 0.11, mid, '${riskName(sl.risk).toUpperCase()} RIDE', faceStyle, faceArc);
        if (sl.start) {
          _arcText(canvas, face - r * 0.2, mid, 'START', faceStyle.copyWith(fontSize: r * 0.075, fontWeight: FontWeight.w700), faceArc);
        }
        _arcText(canvas, face - r * (sl.start ? 0.29 : 0.2), mid, '$doneN/${sl.nodes.length} DONE', faceStyle.copyWith(fontSize: r * 0.042), faceArc);
      } else {
        _arcText(canvas, face - r * 0.11, mid, riskName(sl.risk).toUpperCase(), faceStyle.copyWith(fontSize: r * 0.045), faceArc);
        if (sl.start) {
          _arcText(canvas, face - r * 0.2, mid, 'START', faceStyle.copyWith(fontSize: r * 0.05, fontWeight: FontWeight.w700), faceArc);
        }
      }
    }

    // Hub with the spin cue.
    canvas.drawCircle(c, hub, Paint()..color = kHub);
    canvas.drawCircle(c, hub - 3, Paint()..color = kHubRim..style = PaintingStyle.stroke..strokeWidth = 6);
    // The hub is a crocodile head: eyes peek over its top edge, nostrils below.
    paintCrocoEyes(canvas, Offset(c.dx, c.dy - hub + hub * 0.12), hub * 0.95, kHub);
    for (final dx in [-hub * 0.09, hub * 0.09]) {
      canvas.drawOval(Rect.fromCenter(center: Offset(c.dx + dx, c.dy - hub * 0.2), width: hub * 0.06, height: hub * 0.035), Paint()..color = kHubRim);
    }
    final spin = TextPainter(
      text: TextSpan(text: 'SPIN', style: GoogleFonts.lora(fontSize: r * 0.075, fontWeight: FontWeight.w700, color: Colors.white, letterSpacing: 1.5)),
      textDirection: TextDirection.ltr,
    )..layout();
    final sy = c.dy - hub * 0.46;
    spin.paint(canvas, Offset(c.dx - spin.width / 2, sy - spin.height / 2));
    // Pointer at the top: the slice under it is the selected topic.
    final top = Offset(c.dx, c.dy - r - 4);
    final tri = Path()
      ..moveTo(top.dx - 11, top.dy - 12)
      ..lineTo(top.dx + 11, top.dy - 12)
      ..lineTo(top.dx, top.dy + 4)
      ..close();
    canvas.drawPath(tri, Paint()..color = kPrimary);
    canvas.drawPath(tri, Paint()..color = Colors.white..style = PaintingStyle.stroke..strokeWidth = 2);
  }

  @override
  bool shouldRepaint(covariant _WheelPainter old) => true;
}

// ---------------------------------------------------------------------------
// List view alternative to the wheel (inclusive mode).

class _SlicePicker extends StatelessWidget {
  final List<Slice> slices;
  _SlicePicker({required this.slices});
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
            for (final sl in slices)
              Padding(
                padding: EdgeInsets.only(right: 8),
                child: ChoiceChip(
                  selected: sl.key == s.selectedSlice,
                  onSelected: (_) => s.selectSlice(sl.key, bySpin: true),
                  label: Column(mainAxisSize: MainAxisSize.min, children: [
                    Text(sl.label.split(' ').take(2).join(' ')),
                    Text('${riskName(sl.risk)} · ${(s.sliceProgress(sl) * 100).round()}%', style: TextStyle(fontSize: 11, color: kMuted)),
                  ]),
                ),
              ),
          ]),
        ),
      ]),
    );
  }
}

/// Daily scenario (idea from Basis): one question a day for bonus XP.
void _openDaily(BuildContext context, AppState s) {
  final q = s.roadmap!.slice('money_market').nodes[1].questions[1];
  showDialog(
    context: context,
    builder: (ctx) => SimpleDialog(
      title: Text(q.q),
      contentPadding: EdgeInsets.all(16),
      children: [
        for (final (i, o) in q.options.indexed)
          Padding(
            padding: EdgeInsets.only(bottom: 8),
            child: OutlinedButton(
              onPressed: () {
                final ok = i == q.answer;
                s.answerDaily(ok);
                Navigator.of(ctx).pop();
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('${ok ? 'Correct' : 'Not quite'}: ${q.why}')));
              },
              child: Text(o),
            ),
          ),
      ],
    ),
  );
}
