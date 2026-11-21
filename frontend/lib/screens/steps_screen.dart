// "Build your plan": a drag-and-drop question with Scratch-style blocks.
// Drag any number of step blocks, in any order, under the "When this happens"
// block; they snap together like jigsaw pieces. Reorder by dragging the handle,
// remove with the cross. Scored here against the expected plan until the
// backend scores block tasks (drafts in assets/steps.json).

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../data/sfx.dart';
import '../widgets/common.dart';

/// Loads the draft plan task for a skill, or null when it has none.
Future<Map<String, dynamic>?> loadStepsTask(String nodeId) async {
  final all = jsonDecode(await rootBundle.loadString('assets/steps.json'))['tasks'] as Map<String, dynamic>;
  final t = all[nodeId];
  return t == null ? null : Map<String, dynamic>.from(t);
}

class StepsScreen extends StatefulWidget {
  final Map<String, dynamic> task;
  StepsScreen({super.key, required this.task});
  @override
  State<StepsScreen> createState() => _StepsScreenState();
}

class _StepsScreenState extends State<StepsScreen> {
  late final List<String> steps = List<String>.from(widget.task['steps']);
  late final List<String> traps = List<String>.from(widget.task['traps']);
  late final List<String> palette = ([...steps, ...traps]..sort((a, b) => a.hashCode.compareTo(b.hashCode)));
  final List<String> plan = [];
  bool submitted = false;
  double score = 0;

  void _add(String b) {
    if (submitted || plan.contains(b)) return;
    setState(() => plan.add(b));
  }

  // Score: share of expected steps placed in the right relative order (longest
  // common subsequence), minus a penalty for each block that does not belong.
  void _submit() {
    final n = plan.length, m = steps.length;
    final lcs = List.generate(n + 1, (_) => List.filled(m + 1, 0));
    for (var i = 1; i <= n; i++) {
      for (var j = 1; j <= m; j++) {
        lcs[i][j] = plan[i - 1] == steps[j - 1] ? lcs[i - 1][j - 1] + 1 : (lcs[i - 1][j] > lcs[i][j - 1] ? lcs[i - 1][j] : lcs[i][j - 1]);
      }
    }
    final wrong = plan.where(traps.contains).length;
    score = ((lcs[n][m] / m) - 0.25 * wrong).clamp(0, 1).toDouble();
    setState(() => submitted = true);
    score >= 0.8 ? Sfx.correct() : Sfx.wrong();
    if (score >= 0.8) context.read<AppState>().addXp(Rewards.correctAnswer);
  }

  @override
  Widget build(BuildContext context) {
    final t = widget.task;
    return Scaffold(
      appBar: AppBar(title: Text('Build your plan')),
      body: ListView(padding: EdgeInsets.fromLTRB(20, 8, 20, 32), children: [
        Text('BUILD YOUR PLAN', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, letterSpacing: .6, color: kPrimaryText)),
        SizedBox(height: 6),
        Text(t['q'] as String, style: TextStyle(fontSize: 21, fontWeight: FontWeight.w800, height: 1.25, color: kInk)),
        SizedBox(height: 6),
        Text('Drag the steps you would take under the first block, in order. Use as many as you need.', style: TextStyle(color: kMuted)),
        SizedBox(height: 16),
        // The plan: a hat block, then the snapped blocks, then a drop slot.
        DragTarget<String>(
          onAcceptWithDetails: (d) => _add(d.data),
          builder: (context, cand, _) => AnimatedContainer(
            duration: Duration(milliseconds: 150),
            padding: EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: cand.isNotEmpty ? kPrimarySoft : kSurface,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: cand.isNotEmpty ? kPrimary : kLine, width: 2),
            ),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              PuzzleBlock(text: 'When this happens', hat: true),
              ReorderableListView(
                shrinkWrap: true,
                physics: NeverScrollableScrollPhysics(),
                buildDefaultDragHandles: false,
                onReorder: submitted
                    ? (_, __) {}
                    : (a, b) => setState(() {
                          if (b > a) b--;
                          plan.insert(b, plan.removeAt(a));
                        }),
                children: [
                  for (final (i, b) in plan.indexed)
                    Transform.translate(
                      key: ValueKey(b),
                      // overlap by the tab height so each tab fills the notch below it
                      offset: Offset(0, -8.0 * (i + 1)),
                      child: PuzzleBlock(
                        text: b,
                        mark: !submitted ? null : steps.contains(b) ? true : false,
                        leading: submitted ? null : ReorderableDragStartListener(index: i, child: Icon(Icons.drag_indicator, color: Colors.white70, size: 20)),
                        trailing: submitted
                            ? null
                            : InkWell(onTap: () => setState(() => plan.remove(b)), child: Icon(Icons.close, color: Colors.white, size: 18)),
                      ),
                    ),
                ],
              ),
              if (!submitted)
                Transform.translate(
                  offset: Offset(0, -8.0 * plan.length),
                  child: Container(
                    height: 46,
                    margin: EdgeInsets.only(top: 4),
                    alignment: Alignment.center,
                    decoration: BoxDecoration(borderRadius: BorderRadius.circular(10), border: Border.all(color: kBorder, width: 1.5)),
                    child: Text(plan.isEmpty ? 'Drop your first step here' : 'Drop the next step here', style: TextStyle(color: kMuted, fontSize: 13)),
                  ),
                ),
            ]),
          ),
        ),
        SizedBox(height: 18),
        if (!submitted) ...[
          Text('Steps', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
          SizedBox(height: 8),
          for (final b in palette)
            if (!plan.contains(b))
              Padding(
                padding: EdgeInsets.only(bottom: 8),
                child: LayoutBuilder(
                  builder: (context, c) => Draggable<String>(
                    data: b,
                    feedback: Material(color: Colors.transparent, child: SizedBox(width: c.maxWidth, child: PuzzleBlock(text: b, lifted: true))),
                    childWhenDragging: Opacity(opacity: 0.3, child: PuzzleBlock(text: b, muted: true)),
                    child: GestureDetector(onTap: () => _add(b), child: PuzzleBlock(text: b, muted: true)),
                  ),
                ),
              ),
          SizedBox(height: 12),
          FilledButton(onPressed: plan.isEmpty ? null : _submit, child: Text('Check my plan')),
        ] else ...[
          Panel(
            color: score >= 0.8 ? kGreenSoft : kWarnSoft,
            border: score >= 0.8 ? kGreen : kWarnBorder,
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(score >= 0.8 ? 'Strong plan! +${Rewards.correctAnswer} Emeralds' : 'Score: ${(score * 100).round()}%',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: score >= 0.8 ? kGreen : kWarnText)),
              SizedBox(height: 6),
              Text(t['why'] as String, style: TextStyle(color: kBody, height: 1.4)),
            ]),
          ),
          SizedBox(height: 14),
          Text('A good plan', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
          SizedBox(height: 8),
          PuzzleBlock(text: 'When this happens', hat: true),
          for (final (i, b) in steps.indexed) Transform.translate(offset: Offset(0, -8.0 * (i + 1)), child: PuzzleBlock(text: b)),
          SizedBox(height: 20),
          FilledButton(onPressed: () => Navigator.of(context).pop(score), child: Text('Done')),
        ],
      ]),
    );
  }
}

/// A Scratch-style block: a notch on top and a tab underneath, so stacked
/// blocks look like they fit together. [hat] is the rounded starting block.
class PuzzleBlock extends StatelessWidget {
  final String text;
  final bool hat, muted, lifted;
  final bool? mark; // after checking: true = belongs, false = does not
  final Widget? leading, trailing;
  PuzzleBlock({super.key, required this.text, this.hat = false, this.muted = false, this.lifted = false, this.mark, this.leading, this.trailing});

  @override
  Widget build(BuildContext context) {
    final color = hat
        ? Color(0xFF0B6B26)
        : mark == false
            ? Color(0xFFC2410C)
            : muted
                ? Color(0xFF3FAE3A)
                : kPrimary;
    return CustomPaint(
      painter: _BlockPainter(color, hat: hat, shadow: lifted),
      child: Container(
        constraints: BoxConstraints(minHeight: hat ? 52 : 46),
        padding: EdgeInsets.fromLTRB(12, hat ? 16 : 12, 12, 16),
        child: Row(children: [
          if (leading != null) ...[leading!, SizedBox(width: 6)],
          if (hat) ...[Icon(Icons.flag_rounded, color: Color(0xFFFFE08A), size: 18), SizedBox(width: 6)],
          Expanded(child: Text(text, style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 14))),
          if (mark != null) Icon(mark! ? Icons.check_circle : Icons.cancel, color: Colors.white, size: 20),
          if (trailing != null) ...[SizedBox(width: 6), trailing!],
        ]),
      ),
    );
  }
}

class _BlockPainter extends CustomPainter {
  final Color color;
  final bool hat, shadow;
  _BlockPainter(this.color, {this.hat = false, this.shadow = false});

  @override
  void paint(Canvas canvas, Size size) {
    const r = 8.0, tab = 8.0, nx = 18.0, nw = 22.0;
    final w = size.width, h = size.height - tab; // the tab hangs below
    final p = Path();
    if (hat) {
      p.moveTo(0, 14);
      p.quadraticBezierTo(w * 0.15, -4, w * 0.32, 10);
      p.lineTo(w - r, 10);
      p.quadraticBezierTo(w, 10, w, 10 + r);
    } else {
      p.moveTo(0, r);
      p.quadraticBezierTo(0, 0, r, 0);
      // notch where the block above snaps in
      p.lineTo(nx, 0);
      p.lineTo(nx + 5, tab);
      p.lineTo(nx + nw - 5, tab);
      p.lineTo(nx + nw, 0);
      p.lineTo(w - r, 0);
      p.quadraticBezierTo(w, 0, w, r);
    }
    p.lineTo(w, h - r);
    p.quadraticBezierTo(w, h, w - r, h);
    // tab that fits the next block's notch
    p.lineTo(nx + nw, h);
    p.lineTo(nx + nw - 5, h + tab);
    p.lineTo(nx + 5, h + tab);
    p.lineTo(nx, h);
    p.lineTo(r, h);
    p.quadraticBezierTo(0, h, 0, h - r);
    p.close();
    if (shadow) canvas.drawShadow(p, Colors.black, 6, false);
    canvas.drawPath(p, Paint()..color = color);
    canvas.drawPath(p, Paint()..color = Colors.black.withValues(alpha: 0.18)..style = PaintingStyle.stroke..strokeWidth = 1.2);
  }

  @override
  bool shouldRepaint(covariant _BlockPainter old) => old.color != color || old.hat != hat || old.shadow != shadow;
}
