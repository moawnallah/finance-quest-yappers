// Quick check (idea from Basis): the 5 questions based on the EU Eurobarometer
// 525 financial-literacy survey (2023), each with "I don't know". The result
// compares the score with Poland and the EU and marks the slices to focus on.
// The same screen runs again as a retest (?retest=1) to show before vs after.

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../widgets/common.dart';

class PlacementScreen extends StatefulWidget {
  final bool retest;
  PlacementScreen({super.key, this.retest = false});
  @override
  State<PlacementScreen> createState() => _PlacementScreenState();
}

class _PlacementScreenState extends State<PlacementScreen> {
  int i = 0;
  int? picked; // -1 = I don't know; set once the answer is revealed
  int? chosen; // the option picked, before "How sure are you?" reveals the answer
  final Map<String, int> sure = {}; // question id -> confidence 1-5
  int score = 0;
  bool done = false;
  final List<String> missed = [];
  final Map<String, bool?> answers = {}; // question id -> right, wrong, or null for "I don't know

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final qs = s.placement;
    if (qs.isEmpty) return Scaffold(body: Center(child: CircularProgressIndicator()));
    if (done) return _result(context, s, qs.length);
    final q = qs[i];
    final title = widget.retest ? 'Check your progress' : 'Quick check';
    return Scaffold(
      appBar: AppBar(title: Text(title), actions: [
        // Skipping still sends the survey (with the answers so far), so the Path tab has a path.
        if (!widget.retest)
          TextButton(
            onPressed: () {
              s.submitSurvey(answers, sure);
              context.go('/path');
            },
            child: Text('Skip'),
          ),
      ]),
      body: ListView(padding: EdgeInsets.all(20), children: [
        LinearProgressIndicator(value: (i + (picked != null ? 1 : 0)) / qs.length, minHeight: 8, color: kPrimary),
        SizedBox(height: 16),
        Text('QUESTION ${i + 1} OF ${qs.length} · ${s.placementTopic[q.id] ?? ''}',
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: kPrimaryText)),
        SizedBox(height: 8),
        Text(q.q, style: TextStyle(fontSize: 21, fontWeight: FontWeight.w800, height: 1.3)),
        SizedBox(height: 16),
        for (final (k, o) in [...q.options, "I don't know"].indexed)
          Padding(
            padding: EdgeInsets.only(bottom: 10),
            child: _option(q, k == q.options.length ? -1 : k, o),
          ),
        if (chosen != null && picked == null) ...[
          Text('How sure are you?', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
          SizedBox(height: 8),
          Row(children: [
            for (final c in [1, 2, 3, 4, 5])
              Expanded(
                child: Padding(
                  padding: EdgeInsets.symmetric(horizontal: 3),
                  child: OutlinedButton(
                    style: OutlinedButton.styleFrom(minimumSize: Size(0, 48), padding: EdgeInsets.zero),
                    onPressed: () => setState(() => _reveal(q, chosen!, c)),
                    child: Text('$c'),
                  ),
                ),
              ),
          ]),
          SizedBox(height: 4),
          Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            Text('Guessing', style: TextStyle(fontSize: 12, color: kMuted)),
            Text('Certain', style: TextStyle(fontSize: 12, color: kMuted)),
          ]),
        ],
        if (picked != null) ...[
          Panel(
            child: Text(
              '${picked == q.answer ? 'Correct.' : picked == -1 ? 'Good call to say so.' : 'Not quite.'} ${q.why ?? ''}',
              style: TextStyle(height: 1.4, color: kBody),
            ),
          ),
          SizedBox(height: 16),
          FilledButton(
            onPressed: () => setState(() {
              if (i < qs.length - 1) {
                i++;
                picked = null;
                chosen = null;
              } else {
                done = true;
                s.finishPlacement(score, missed, retest: widget.retest, answers: answers, sure: sure);
              }
            }),
            child: Text(i < qs.length - 1 ? 'Next' : 'See my result'),
          ),
        ],
      ]),
    );
  }

  void _reveal(q, int k, int? confidence) {
    picked = k;
    answers[q.id] = k == -1 ? null : k == q.answer;
    if (confidence != null) sure[q.id] = confidence;
    if (k == q.answer) {
      score++;
    } else {
      missed.add(q.id);
    }
  }

  Widget _option(q, int k, String label) {
    final isAnswer = k == q.answer, isPicked = k == picked;
    return OutlinedButton(
      style: OutlinedButton.styleFrom(
        minimumSize: Size.fromHeight(56),
        alignment: Alignment.centerLeft,
        backgroundColor: picked == null ? (k == chosen ? kPrimarySoft : null) : isAnswer ? kGreenSoft : isPicked ? kRedSoft : null,
        side: BorderSide(color: picked == null ? (k == chosen ? kPrimary : kBorder) : isAnswer ? kGreen : isPicked ? kRed : kBorder, width: 1.5),
      ),
      onPressed: picked != null
          ? null
          : () => setState(() {
                if (k == -1) {
                  _reveal(q, -1, null); // "I don't know" needs no confidence
                } else {
                  chosen = k; // ask "How sure are you?" before showing the answer
                }
              }),
      child: Text(label, style: TextStyle(color: k == -1 ? kMuted : kInk, fontSize: 15, fontStyle: k == -1 ? FontStyle.italic : null)),
    );
  }

  Widget _result(BuildContext context, AppState s, int total) {
    final band = score >= 4 ? 'high_4_or_5_correct' : score >= 2 ? 'medium_2_or_3_correct' : 'low_0_or_1_correct';
    final bandLabel = score >= 4 ? '4 or 5 correct' : score >= 2 ? '2 or 3 correct' : '0 or 1 correct';
    final b = Map<String, dynamic>.from(s.bands[band] ?? {});
    final before = s.profile.placementScore;
    final focus = s.focusSlices.map((k) => panelLabels[k] ?? k).toList();
    return Scaffold(
      appBar: AppBar(title: Text(widget.retest ? 'Your progress' : 'Your starting point')),
      body: ListView(padding: EdgeInsets.all(20), children: [
        Center(child: MascotPlaceholder(size: 200, pose: score >= 3 ? 'cheer' : 'think')),
        SizedBox(height: 8),
        Center(child: Text('$score of $total', style: TextStyle(fontSize: 48, fontWeight: FontWeight.w800, color: kPrimaryText))),
        if (widget.retest && before != null)
          Center(
            child: Text('First check: $before of $total · now: $score of $total',
                style: TextStyle(fontWeight: FontWeight.w700, color: score >= before ? kGreen : kMuted)),
          ),
        SizedBox(height: 16),
        Panel(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('How people answered the same questions', style: TextStyle(fontWeight: FontWeight.w700)),
            SizedBox(height: 8),
            Text('You are in the "$bandLabel" group.', style: TextStyle(color: kBody)),
            SizedBox(height: 10),
            _bar('Poland', b['pl'] ?? 0),
            SizedBox(height: 6),
            _bar('EU', b['eu'] ?? 0),
            SizedBox(height: 8),
            Text('Share of adults in the same group. Based on the EU Eurobarometer 525 financial-literacy questions (2023).',
                style: TextStyle(fontSize: 11, color: kMuted)),
          ]),
        ),
        if (!widget.retest && focus.isNotEmpty) ...[
          SizedBox(height: 12),
          Panel(
            color: kPrimarySoft,
            border: kPrimarySoft,
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Your focus on the wheel', style: TextStyle(fontWeight: FontWeight.w700, color: kPrimaryText)),
              SizedBox(height: 4),
              Text('The questions you missed point to: ${focus.join(', ')}. Their roadmaps are marked as your focus.',
                  style: TextStyle(color: kBody)),
            ]),
          ),
        ],
        if (!widget.retest) ...[
          SizedBox(height: 20),
          Text('Daily goal (Scales)', style: TextStyle(fontWeight: FontWeight.w700)),
          SizedBox(height: 8),
          DailyGoalPicker(),
        ],
        SizedBox(height: 24),
        FilledButton(
          onPressed: () => context.go(widget.retest ? '/progress' : '/path'),
          child: Text(widget.retest ? 'Back to my progress' : 'Go to my path'),
        ),
      ]),
    );
  }

  Widget _bar(String label, num pct) => Row(children: [
        SizedBox(width: 56, child: Text(label, style: TextStyle(fontWeight: FontWeight.w600))),
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: LinearProgressIndicator(value: pct / 100, minHeight: 12, color: kPrimary, backgroundColor: kLine),
          ),
        ),
        SizedBox(width: 8),
        SizedBox(width: 40, child: Text('$pct%', textAlign: TextAlign.right)),
      ]);
}
