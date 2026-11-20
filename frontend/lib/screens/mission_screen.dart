// A mission = one node: its questions one by one.
// - Scored questions: pick an option, then see why (AI tutor bubble).
// - Behaviour questions: every option gets its own feedback, nothing is "wrong".
// - Reflection questions: personal, not scored.
// In the real app the answer is checked by POST /answers and the tutor text comes
// from POST /tutor; here the stored `why` plus the learner's goal is used.

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../models/content.dart';
import '../widgets/common.dart';

class MissionScreen extends StatefulWidget {
  final String sliceKey;
  final String nodeId;
  MissionScreen({super.key, required this.sliceKey, required this.nodeId});
  @override
  State<MissionScreen> createState() => _MissionScreenState();
}

class _MissionScreenState extends State<MissionScreen> {
  int card = 0; // lesson cards come first (idea from Basis and Finanz)
  bool learning = true;
  int index = 0;
  int? picked;
  int correct = 0;

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final slice = s.roadmap!.slice(widget.sliceKey);
    final node = slice.nodes.firstWhere((n) => n.id == Uri.decodeComponent(widget.nodeId));
    final cards = [for (final q in node.questions) if (q.why != null) q];
    if (learning && cards.isNotEmpty) return _learnCard(context, node.title, cards, riskColor(slice.risk), slice.label);
    final q = node.questions[index];
    final answered = picked != null;
    final last = index == node.questions.length - 1;

    return Scaffold(
      appBar: AppBar(
        title: Text(node.title),
        leading: IconButton(icon: Icon(Icons.close), tooltip: 'Close mission', onPressed: () => context.pop()),
      ),
      body: ListView(padding: EdgeInsets.all(20), children: [
        LinearProgressIndicator(value: (index + (answered ? 1 : 0)) / node.questions.length, minHeight: 8, color: kPrimary),
        SizedBox(height: 20),
        Text(
          q.isScored ? 'QUESTION ${index + 1} OF ${node.questions.length}' : q.isBehaviour ? 'WHAT WOULD YOU DO?' : 'ABOUT YOU',
          style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, letterSpacing: .6, color: kPrimaryText),
        ),
        SizedBox(height: 8),
        Text(q.q, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, height: 1.25)),
        SizedBox(height: 16),
        // Answer by tapping an option, or by dragging it into the box.
        if (!answered)
          DragTarget<int>(
            onAcceptWithDetails: (d) { _pick(q, d.data); s.recordAnswer(node, index); },
            builder: (context, cand, _) => AnimatedContainer(
              duration: Duration(milliseconds: 150),
              height: 64,
              margin: EdgeInsets.only(bottom: 14),
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: cand.isNotEmpty ? kPrimarySoft : Colors.transparent,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: cand.isNotEmpty ? kPrimary : kBorder, width: 2),
              ),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.pan_tool_alt_outlined, color: kMuted, size: 20),
                SizedBox(width: 8),
                Text(cand.isNotEmpty ? 'Drop it here' : 'Drag your answer here, or tap it', style: TextStyle(color: kMuted)),
              ]),
            ),
          ),
        for (final (i, o) in q.options.indexed)
          answered
              ? _OptionTile(text: o, state: _optionState(q, i))
              : LayoutBuilder(
                  builder: (context, c) => Draggable<int>(
                    data: i,
                    feedback: Material(
                      color: Colors.transparent,
                      child: SizedBox(width: c.maxWidth, child: Opacity(opacity: 0.9, child: _OptionTile(text: o, state: 'picked'))),
                    ),
                    childWhenDragging: Opacity(opacity: 0.35, child: _OptionTile(text: o, state: 'idle')),
                    child: _OptionTile(text: o, state: 'idle', onTap: () { _pick(q, i); s.recordAnswer(node, index); }, draggable: true),
                  ),
                ),
        if (answered) ...[
          SizedBox(height: 8),
          if (q.isScored && picked == q.answer)
            Align(
              alignment: Alignment.centerLeft,
              child: Container(
                margin: EdgeInsets.only(bottom: 8),
                padding: EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(color: kPrimarySoft, borderRadius: BorderRadius.circular(999)),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  ScaleIcon(size: 16),
                  SizedBox(width: 4),
                  Text('+${Rewards.correctAnswer} Scales', style: TextStyle(fontWeight: FontWeight.w700, color: kPrimaryText)),
                ]),
              ),
            ),
          if (q.isScored) TutorBubble(text: _tutorText(q, s)),
          if (q.isBehaviour) TutorBubble(text: q.feedback![picked!]),
          if (!q.isScored && !q.isBehaviour) Panel(child: Text('Thanks. We use this to tailor your path. There is no right or wrong answer.')),
          if (q.sources.isNotEmpty) ...[
            SizedBox(height: 8),
            Text('Source: ${q.sources.first}', style: TextStyle(fontSize: 11, color: kMuted)),
          ],
          SizedBox(height: 16),
          FilledButton(
            onPressed: () {
              if (last) {
                s.completeNode(node, correct);
                context.go('/result');
              } else {
                setState(() { index++; picked = null; });
              }
            },
            child: Text(last ? 'Finish mission' : 'Continue'),
          ),
        ],
      ]),
    );
  }

  Widget _learnCard(BuildContext context, String title, List<Question> cards, Color accent, String sliceLabel) {
    final c = cards[card];
    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        leading: IconButton(icon: Icon(Icons.close), tooltip: 'Close mission', onPressed: () => context.pop()),
      ),
      body: ListView(padding: EdgeInsets.all(20), children: [
        LinearProgressIndicator(value: (card + 1) / (cards.length + 1), minHeight: 8, color: kPrimary),
        SizedBox(height: 16),
        Text('KEY IDEA ${card + 1} OF ${cards.length} · $sliceLabel',
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: kPrimaryText)),
        SizedBox(height: 12),
        Panel(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            // Illustration placeholder: replace with a real illustration or chart per card.
            Container(
              height: 160,
              width: double.infinity,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(14),
                gradient: LinearGradient(colors: [accent.withValues(alpha: 0.18), accent.withValues(alpha: 0.05)]),
              ),
              child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                MascotPlaceholder(size: 72),
                SizedBox(height: 6),
                Text('Illustration placeholder', style: TextStyle(fontSize: 11, color: kMuted)),
              ]),
            ),
            SizedBox(height: 16),
            Text(c.q, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, height: 1.25)),
            SizedBox(height: 10),
            Text(c.why!, style: TextStyle(fontSize: 17, height: 1.45, color: kBody)),
            SizedBox(height: 16),
            // Example placeholder: a short real-life example (in zloty) goes here.
            Container(
              width: double.infinity,
              padding: EdgeInsets.all(12),
              decoration: BoxDecoration(color: kWarnSoft, borderRadius: BorderRadius.circular(12), border: Border.all(color: kWarnBorder)),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Icon(Icons.person_outline, size: 18, color: kWarnIcon),
                SizedBox(width: 8),
                Expanded(child: Text('Example placeholder: a short story about someone like you, with real amounts in zł.',
                    style: TextStyle(fontSize: 13, color: kWarnText))),
              ]),
            ),
            if (c.sources.isNotEmpty) ...[
              SizedBox(height: 10),
              Text('Source: ${Uri.parse(c.sources.first).host}', style: TextStyle(fontSize: 11, color: kMuted)),
            ],
          ]),
        ),
        SizedBox(height: 16),
        Row(children: [
          if (card > 0)
            Expanded(
              child: OutlinedButton(
                style: OutlinedButton.styleFrom(minimumSize: Size.fromHeight(52)),
                onPressed: () => setState(() => card--),
                child: Text('Back'),
              ),
            ),
          if (card > 0) SizedBox(width: 10),
          Expanded(
            flex: 2,
            child: FilledButton(
              onPressed: () => setState(() { if (card < cards.length - 1) { card++; } else { learning = false; } }),
              child: Text(card < cards.length - 1 ? 'Next' : 'Start the questions'),
            ),
          ),
        ]),
      ]),
    );
  }

  void _pick(Question q, int i) => setState(() {
        picked = i;
        if (q.isScored && i == q.answer) correct++;
      });

  String _optionState(Question q, int i) {
    if (picked == null) return 'idle';
    if (q.isScored) {
      if (i == q.answer) return 'correct';
      if (i == picked) return 'wrong';
      return 'idle';
    }
    return i == picked ? 'picked' : 'idle';
  }

  // Draft stand-in for the AI tutor: explain the concept and relate it to the
  // learner's goal, never recommend a product.
  String _tutorText(Question q, AppState s) {
    final right = picked == q.answer;
    final goal = '${s.profile.goal.toLowerCase()} in ${s.profile.horizonYears} years';
    return '${right ? 'Right.' : 'Not quite.'} ${q.why} For your goal ($goal), keep this in mind when you compare options.';
  }
}

class _OptionTile extends StatelessWidget {
  final String text;
  final String state; // idle | correct | wrong | picked
  final VoidCallback? onTap;
  final bool draggable;
  _OptionTile({required this.text, required this.state, this.onTap, this.draggable = false});

  @override
  Widget build(BuildContext context) {
    final (bg, border, icon) = switch (state) {
      'correct' => (kGreenSoft, kGreen, Icons.check),
      'wrong' => (kRedSoft, kRed, Icons.close),
      'picked' => (kPrimarySoft, kPrimary, Icons.radio_button_checked),
      _ => (kSurface, kBorder, null),
    };
    return Padding(
      padding: EdgeInsets.only(bottom: 10),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          constraints: BoxConstraints(minHeight: 56),
          padding: EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(14), border: Border.all(color: border, width: state == 'idle' ? 1 : 2)),
          child: Row(children: [
            if (draggable) ...[Icon(Icons.drag_indicator, size: 18, color: kFaint), SizedBox(width: 6)],
            Expanded(child: Text(text, style: TextStyle(fontSize: 15, color: kInk))),
            if (icon != null) Icon(icon, color: border),
          ]),
        ),
      ),
    );
  }
}
