// Home: the wheel of investment types (Version B). Slices are coloured calm -> bumpy,
// stars mark recommended starts, the outer ring shows progress. A list view is
// available for accessibility (inclusive mode).

import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../models/content.dart';
import '../widgets/common.dart';

class WheelScreen extends StatelessWidget {
  WheelScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final rm = s.roadmap;
    if (rm == null) return Scaffold(body: Center(child: CircularProgressIndicator()));
    return Scaffold(
      appBar: StatsBar(title: 'What to explore', subtitle: 'Hi ${s.profile.name}'),
      body: ListView(padding: EdgeInsets.all(20), children: [
        Panel(
          color: kPrimarySoft,
          border: kPrimarySoft,
          child: Text('Goal: ${s.profile.goal} · horizon ${s.profile.horizonYears} years. Start with the slices marked with a yellow dot.',
              style: TextStyle(color: kPrimaryText, fontWeight: FontWeight.w600)),
        ),
        if (s.focusSlices.isNotEmpty) ...[
          SizedBox(height: 12),
          Text('Your focus from the quick check', style: TextStyle(fontWeight: FontWeight.w700)),
          SizedBox(height: 6),
          Wrap(spacing: 8, runSpacing: 8, children: [
            for (final k in s.focusSlices)
              ActionChip(
                avatar: Icon(Icons.adjust, size: 18, color: kPrimary),
                label: Text(rm.slice(k).label),
                onPressed: () => context.push('/slice/$k'),
              ),
          ]),
        ],
        SizedBox(height: 12),
        _DailyCard(),
        SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: () => context.push('/progress'),
          icon: Icon(Icons.emoji_events_outlined),
          label: Text('Level ${s.level.name} · today ${s.xpToday}/${s.dailyGoal} XP · badges ${s.badges.length}'),
          style: OutlinedButton.styleFrom(minimumSize: Size.fromHeight(48)),
        ),
        SizedBox(height: 12),
        Row(children: [
          Text('Text size'),
          Switch(value: s.largeText, onChanged: s.setLargeText),
          Spacer(),
          SegmentedButton<bool>(
            showSelectedIcon: false,
            style: ButtonStyle(visualDensity: VisualDensity.compact, padding: WidgetStatePropertyAll(EdgeInsets.symmetric(horizontal: 14))),
            segments: [ButtonSegment(value: false, label: Text('Wheel', softWrap: false, overflow: TextOverflow.visible)), ButtonSegment(value: true, label: Text('List', softWrap: false))],
            selected: {s.listView},
            onSelectionChanged: (v) => s.setListView(v.first),
          ),
        ]),
        SizedBox(height: 12),
        if (!s.listView)
          AspectRatio(aspectRatio: 1, child: _Wheel(slices: rm.slices))
        else
          for (final sl in rm.slices) _SliceRow(slice: sl),
        SizedBox(height: 12),
        Text('Colours run from calm (green) to bumpy (dark red). Yellow dot: a good place to start. Blue marker: your focus from the quick check. Typical, educational, not advice.',
            style: TextStyle(fontSize: 12, color: kMuted)),
      ]),
    );
  }
}

/// Daily scenario (idea from Basis): one question a day for bonus XP.
class _DailyCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final q = s.roadmap!.slice('money_market').nodes[1].questions[1];
    return Panel(
      border: Color(0xFFFDB022),
      color: kWarnSoft,
      child: Row(children: [
        Icon(Icons.today, color: kWarnIcon),
        SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text("Today's scenario · +30 XP", style: TextStyle(fontWeight: FontWeight.w700)),
            Text(s.dailyAnswered ? 'Done for today. Come back tomorrow.' : 'One quick question about real prices.',
                style: TextStyle(color: kMuted, fontSize: 13)),
          ]),
        ),
        if (!s.dailyAnswered)
          TextButton(
            onPressed: () => showDialog(
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
            ),
            child: Text('Answer'),
          ),
      ]),
    );
  }
}

class _SliceRow extends StatelessWidget {
  final Slice slice;
  _SliceRow({required this.slice});
  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    return Card(
      elevation: 0,
      child: ListTile(
        minVerticalPadding: 14,
        leading: CircleAvatar(backgroundColor: riskColor(slice.risk), child: Text('${slice.risk}', style: TextStyle(color: Colors.white))),
        title: Text(slice.label, style: TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text('${(s.sliceProgress(slice) * 100).round()}% done${slice.start ? ' · start here' : ''}'),
        trailing: Icon(Icons.chevron_right),
        onTap: () => context.push('/slice/${slice.key}'),
      ),
    );
  }
}

class _Wheel extends StatefulWidget {
  final List<Slice> slices;
  _Wheel({required this.slices});
  @override
  State<_Wheel> createState() => _WheelState();
}

class _WheelState extends State<_Wheel> {
  int? hover;

  int? _hit(Offset p, double size) {
    final v = p - Offset(size / 2, size / 2);
    final r = v.distance / (size / 2);
    if (r < 0.28 || r > 0.95) return null;
    final n = widget.slices.length;
    final step = 2 * math.pi / n;
    var a = math.atan2(v.dy, v.dx) + math.pi / 2 + step / 2;
    a = (a % (2 * math.pi) + 2 * math.pi) % (2 * math.pi);
    return (a / step).floor() % n;
  }

  void _preview(BuildContext context, Slice sl) {
    final s = context.read<AppState>();
    final done = sl.nodes.where((n) => s.doneNodes.contains(n.id)).length;
    showModalBottomSheet(
      context: context,
      showDragHandle: true,
      builder: (ctx) => Padding(
        padding: EdgeInsets.fromLTRB(20, 0, 20, 24),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Container(width: 14, height: 14, decoration: BoxDecoration(color: riskColor(sl.risk), shape: BoxShape.circle)),
            SizedBox(width: 8),
            Expanded(child: Text(sl.label, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800))),
          ]),
          SizedBox(height: 8),
          Text('Risk ${sl.risk} of 5 · ${sl.nodes.length} missions · $done done${sl.start ? ' · recommended start' : ''}',
              style: TextStyle(color: kMuted)),
          SizedBox(height: 12),
          for (final n in sl.nodes.take(4))
            Padding(
              padding: EdgeInsets.only(bottom: 4),
              child: Row(children: [
                Icon(s.doneNodes.contains(n.id) ? Icons.check_circle : s.isUnlocked(n) ? Icons.play_circle_outline : Icons.lock_outline,
                    size: 18, color: kMuted),
                SizedBox(width: 8),
                Expanded(child: Text(n.title)),
              ]),
            ),
          SizedBox(height: 12),
          FilledButton(
            onPressed: () { Navigator.of(ctx).pop(); context.push('/slice/${sl.key}'); },
            child: Text('Open roadmap'),
          ),
        ]),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    return LayoutBuilder(builder: (context, c) {
      final size = c.maxWidth;
      return MouseRegion(
        cursor: hover == null ? SystemMouseCursors.basic : SystemMouseCursors.click,
        onHover: (e) { final h = _hit(e.localPosition, size); if (h != hover) setState(() => hover = h); },
        onExit: (_) => setState(() => hover = null),
        child: GestureDetector(
          onTapUp: (d) {
            final i = _hit(d.localPosition, size);
            if (i == null) return;
            setState(() => hover = i);
            _preview(context, widget.slices[i]);
          },
          child: Semantics(
            label: 'Wheel of ${widget.slices.length} investment types. Tap a slice to preview it, or switch to List for a screen-reader friendly view.',
            child: Stack(alignment: Alignment.center, children: [
              CustomPaint(size: Size(size, size), painter: _WheelPainter(widget.slices, s, hover)),
              if (hover != null)
                Positioned(
                  bottom: 0,
                  child: Container(
                    padding: EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(color: kInk, borderRadius: BorderRadius.circular(999)),
                    child: Text('${widget.slices[hover!].label} · tap to open',
                        style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
                  ),
                ),
            ]),
          ),
        ),
      );
    });
  }
}

class _WheelPainter extends CustomPainter {
  final List<Slice> slices;
  final AppState state;
  final int? hover;
  _WheelPainter(this.slices, this.state, [this.hover]);

  @override
  void paint(Canvas canvas, Size size) {
    final c = Offset(size.width / 2, size.height / 2);
    final rOut = size.width / 2 * 0.92, rIn = size.width / 2 * 0.28;
    final step = 2 * math.pi / slices.length;
    for (var i = 0; i < slices.length; i++) {
      final sl = slices[i];
      final start = -math.pi / 2 - step / 2 + i * step;
      final path = Path()
        ..arcTo(Rect.fromCircle(center: c, radius: rOut), start, step, true)
        ..arcTo(Rect.fromCircle(center: c, radius: rIn), start + step, -step, false)
        ..close();
      canvas.drawPath(path, Paint()..color = riskColor(sl.risk).withValues(alpha: hover == null || hover == i ? 1.0 : 0.55));
      if (hover == i) {
        canvas.drawPath(path, Paint()..color = kInk..style = PaintingStyle.stroke..strokeWidth = 4);
      }
      canvas.drawPath(path, Paint()..color = kBg..style = PaintingStyle.stroke..strokeWidth = 3);
      // progress ring
      final prog = state.sliceProgress(sl);
      final ring = Rect.fromCircle(center: c, radius: rOut + size.width * 0.03);
      canvas.drawArc(ring, start + 0.03, step - 0.06, false, Paint()..color = kLine..style = PaintingStyle.stroke..strokeWidth = 5);
      if (prog > 0) {
        canvas.drawArc(ring, start + 0.03, (step - 0.06) * prog, false,
            Paint()..color = kGreen..style = PaintingStyle.stroke..strokeWidth = 5..strokeCap = StrokeCap.round);
      }
      // label
      final mid = start + step / 2;
      final lr = (rIn + rOut) / 2;
      final pos = c + Offset(math.cos(mid) * lr, math.sin(mid) * lr);
      final label = sl.label.split(' ').take(2).join(' ');
      final tp = TextPainter(
        text: TextSpan(text: label, style: TextStyle(color: Colors.white, fontSize: size.width * 0.028, fontWeight: FontWeight.w700)),
        textAlign: TextAlign.center,
        textDirection: TextDirection.ltr,
      )..layout(maxWidth: size.width * 0.2);
      tp.paint(canvas, pos - Offset(tp.width / 2, tp.height / 2));
      if (sl.start) {
        final bp = c + Offset(math.cos(mid) * (rIn + size.width * 0.05), math.sin(mid) * (rIn + size.width * 0.05));
        canvas.drawCircle(bp, size.width * 0.022, Paint()..color = Color(0xFFFDB022));
        canvas.drawCircle(bp, size.width * 0.022, Paint()..color = Colors.white..style = PaintingStyle.stroke..strokeWidth = 2);
      }
      if (state.focusSlices.contains(sl.key)) {
        // Blue target marker: a topic the quick check says to focus on.
        final fp = c + Offset(math.cos(mid) * (rOut - size.width * 0.05), math.sin(mid) * (rOut - size.width * 0.05));
        canvas.drawCircle(fp, size.width * 0.026, Paint()..color = kPrimary);
        canvas.drawCircle(fp, size.width * 0.026, Paint()..color = Colors.white..style = PaintingStyle.stroke..strokeWidth = 2);
        canvas.drawCircle(fp, size.width * 0.009, Paint()..color = Colors.white);
      }
    }
    canvas.drawCircle(c, rIn - 4, Paint()..color = appDark ? const Color(0xFF2A3146) : const Color(0xFF101828));
    final tp = TextPainter(
      text: TextSpan(text: 'What do\nyou own?', style: TextStyle(color: Colors.white, fontSize: size.width * 0.04, fontWeight: FontWeight.w800)),
      textAlign: TextAlign.center,
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, c - Offset(tp.width / 2, tp.height / 2));
  }

  @override
  bool shouldRepaint(covariant _WheelPainter old) => true;
}
