// Runs a list of engine tasks one by one (GET /tasks/{id}, POST /tasks/{id}/attempts).
// - Easy items: single, multi, true_false, numeric, reflection.
// - Medium day-X tasks: a chart cut at day X, a direction guess and 2-3 reasons.
// The app never knows the answer before submitting: the reveal comes back with the score.

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../data/sfx.dart';
import '../widgets/common.dart';
import 'skills_screen.dart' show ErrorPanel;

/// What to run: task ids in order, and for a drawn test its context and node.
class TaskRun {
  final String title;
  final List<String> taskIds;
  final String context; // practice | prerequisite | test_out
  final String? forNode;
  final String? skill; // the mission this run belongs to, so progress is remembered
  final int doneBefore; // questions already finished in this mission (resume)
  TaskRun({required this.title, required this.taskIds, this.context = 'practice', this.forNode, this.skill, this.doneBefore = 0});
}

class TaskRunScreen extends StatefulWidget {
  final TaskRun run;
  TaskRunScreen({super.key, required this.run});
  @override
  State<TaskRunScreen> createState() => _TaskRunScreenState();
}

class _TaskRunScreenState extends State<TaskRunScreen> {
  int index = 0;
  late Future<Map<String, dynamic>> current;
  DateTime startedAt = DateTime.now();

  // the answer being built
  Object? answer;
  final Set<int> multi = {};
  final Set<String> reasons = {};
  int? confidence;
  bool sending = false;

  // after submitting
  Map<String, dynamic>? result;
  final List<double> scores = [];
  Map<String, dynamic>? lastStatus;
  bool completedNode = false;
  int earned = 0; // Scales earned in this run
  final List<(int, double)> confScore = []; // (how sure 1-5, score 0-1) per scored answer

  @override
  void initState() {
    super.initState();
    current = _load();
  }

  Future<Map<String, dynamic>> _load() {
    final s = context.read<AppState>();
    startedAt = DateTime.now();
    return s.api.task(s.profile.name, widget.run.taskIds[index]);
  }

  void _next() {
    // Finishing the run records one confidence-vs-score point for Progress.
    if (index + 1 >= widget.run.taskIds.length && confScore.isNotEmpty) {
      final c = confScore.map((e) => e.$1).reduce((a, b) => a + b) / confScore.length;
      final sc = confScore.map((e) => e.$2).reduce((a, b) => a + b) / confScore.length;
      context.read<AppState>().addCalibration(widget.run.title, c, sc);
    }
    setState(() {
      index++;
      answer = null;
      multi.clear();
      reasons.clear();
      confidence = null;
      result = null;
      if (index < widget.run.taskIds.length) current = _load();
    });
  }

  Future<void> _submit(Map<String, dynamic> t) async {
    final s = context.read<AppState>();
    final level = t['level'] as String;
    final task = t['task'] as Map<String, dynamic>;
    setState(() => sending = true);
    try {
      final r = await s.api.submit(
        s.profile.name,
        task['id'] as String,
        response: level == 'easy' && task['kind'] == 'multi' ? (multi.toList()..sort()) : answer,
        reasons: level == 'medium' ? reasons.toList() : null,
        confidence: confidence,
        context: widget.run.context,
        forNode: widget.run.forNode,
        startedAt: startedAt,
      );
      final score = (r['score'] as num?)?.toDouble();
      if (widget.run.skill != null) s.markAnswered(widget.run.skill!, task['id'] as String);
      if (score != null) {
        scores.add(score);
        if (confidence != null) confScore.add((confidence!, score));
        score >= 1 ? Sfx.correct() : Sfx.wrong();
      }
      if (score == 1) {
        s.addXp(Rewards.correctAnswer);
        earned += Rewards.correctAnswer;
      }
      if (r['node_completed'] == true) {
        completedNode = true;
        s.addXp(Rewards.missionDone);
        earned += Rewards.missionDone;
        s.earn('first_steps');
      }
      setState(() {
        result = r;
        lastStatus = r['status'] as Map<String, dynamic>;
      });
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  bool _ready(Map<String, dynamic> t) {
    final task = t['task'] as Map<String, dynamic>;
    final needsConfidence = task['confidence'] != null;
    if (needsConfidence && confidence == null) return false;
    if (t['level'] == 'medium') {
      final pick = task['reasons']['pick'];
      return answer != null && reasons.length >= (pick['min'] as int) && reasons.length <= (pick['max'] as int);
    }
    return task['kind'] == 'multi' ? multi.isNotEmpty : answer != null;
  }

  @override
  Widget build(BuildContext context) {
    final total = widget.run.taskIds.length;
    if (index >= total) return _summary(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.run.title),
        leading: IconButton(icon: Icon(Icons.close), tooltip: 'Close', onPressed: () => context.pop()),
      ),
      body: AnimatedSwitcher(
        duration: Duration(milliseconds: 320),
        switchInCurve: Curves.easeOutCubic,
        switchOutCurve: Curves.easeInCubic,
        transitionBuilder: (child, a) {
          final incoming = child.key == ValueKey(index);
          return SlideTransition(
            position: Tween(begin: Offset(incoming ? 1 : -1, 0), end: Offset.zero).animate(a),
            child: child,
          );
        },
        child: KeyedSubtree(key: ValueKey(index), child: FutureBuilder<Map<String, dynamic>>(
        future: current,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) return Center(child: CircularProgressIndicator());
          if (snap.hasError) return ErrorPanel(message: '${snap.error}', onRetry: () => setState(() => current = _load()));
          final t = snap.data!;
          final task = t['task'] as Map<String, dynamic>;
          final medium = t['level'] == 'medium';
          final done = result != null;
          return ListView(padding: EdgeInsets.all(20), children: [
            LinearProgressIndicator(
              value: (widget.run.doneBefore + index + (done ? 1 : 0)) / (widget.run.doneBefore + total),
              minHeight: 8, color: kPrimary, borderRadius: BorderRadius.circular(4),
            ),
            SizedBox(height: 16),
            Text(
              medium ? 'DAY X · ${widget.run.doneBefore + index + 1} OF ${widget.run.doneBefore + total}' : '${_kindLabel(task)} · ${widget.run.doneBefore + index + 1} OF ${widget.run.doneBefore + total}',
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, letterSpacing: .6, color: kPrimaryText),
            ),
            SizedBox(height: 8),
            if (medium) ..._medium(task) else ..._easy(task),
            if (task['confidence'] != null && !done) ...[
              SizedBox(height: 20),
              Text('How sure are you?', style: TextStyle(fontWeight: FontWeight.w700)),
              SizedBox(height: 8),
              _ConfidencePicker(value: confidence, onChanged: (v) => setState(() => confidence = v)),
            ],
            SizedBox(height: 20),
            if (!done)
              FilledButton(
                style: FilledButton.styleFrom(minimumSize: Size.fromHeight(52)),
                onPressed: _ready(t) && !sending ? () => _submit(t) : null,
                child: Text(sending ? 'Checking...' : 'Check my answer'),
              )
            else
              FilledButton(
                style: FilledButton.styleFrom(minimumSize: Size.fromHeight(52)),
                onPressed: _next,
                child: Text(index == total - 1 ? 'Finish' : 'Next'),
              ),
          ]);
        },
      )),
      ),
    );
  }

  String _kindLabel(Map<String, dynamic> task) => switch (task['kind']) {
        'reflection' => 'WHAT WOULD YOU DO?',
        'multi' => 'PICK ALL THAT APPLY',
        'true_false' => 'TRUE OR FALSE',
        'numeric' => 'ESTIMATE',
        _ => 'QUESTION',
      };

  // ---------------------------------------------------------------- easy items

  List<Widget> _easy(Map<String, dynamic> task) {
    final kind = task['kind'] as String;
    final reveal = result?['reveal'] as Map<String, dynamic>?;
    final options = (task['options'] as List? ?? []).cast<String>();
    final out = <Widget>[
      Text(task['q'] as String, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, height: 1.25)),
      SizedBox(height: 16),
    ];
    switch (kind) {
      case 'single':
      case 'reflection':
      case 'multi':
        final correct = reveal == null || kind == 'reflection'
            ? <int>{}
            : (reveal['answer'] is List ? (reveal['answer'] as List).cast<int>().toSet() : {reveal['answer'] as int});
        for (var i = 0; i < options.length; i++) {
          final picked = kind == 'multi' ? multi.contains(i) : answer == i;
          out.add(_OptionTile(
            text: options[i],
            picked: picked,
            multi: kind == 'multi',
            state: reveal == null ? null : (correct.contains(i) ? true : (picked && kind != 'reflection' ? false : null)),
            onTap: reveal != null
                ? null
                : () => setState(() {
                      if (kind == 'multi') {
                        multi.contains(i) ? multi.remove(i) : multi.add(i);
                      } else {
                        answer = i;
                      }
                    }),
          ));
        }
      case 'true_false':
        out.add(Row(children: [
          for (final v in [true, false]) ...[
            Expanded(
              child: _OptionTile(
                text: v ? 'True' : 'False',
                picked: answer == v,
                state: reveal == null ? null : (reveal['answer'] == v ? true : (answer == v ? false : null)),
                onTap: reveal != null ? null : () => setState(() => answer = v),
              ),
            ),
            if (v) SizedBox(width: 10),
          ],
        ]));
      case 'numeric':
        out.add(_NumericInput(
          task: task,
          value: answer as num?,
          enabled: reveal == null,
          onChanged: (v) => setState(() => answer = v),
        ));
    }
    if (reveal != null) {
      out.add(SizedBox(height: 12));
      out.add(_ScoreBanner(score: (result!['score'] as num?)?.toDouble(), scored: kind != 'reflection'));
      if (kind == 'numeric') {
        out.add(Padding(
          padding: EdgeInsets.only(top: 8),
          child: Text('Answer: ${_fmt(reveal['answer'] as num)} ${reveal['unit'] ?? ''}   ·   yours: ${_fmt(answer as num)}',
              style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
        ));
      }
      final feedback = kind == 'reflection' ? (reveal['feedback'] as List)[answer as int] as String : null;
      final why = feedback ?? reveal['why'] as String?;
      if (why != null) out.addAll([SizedBox(height: 12), TutorBubble(text: why, onAsk: () => _askTutor(task, reveal, why))]);
    }
    return out;
  }

  /// Opens the tutor chat with this question, the user's answer, the right
  /// answer and the explanation.
  void _askTutor(Map<String, dynamic> task, Map<String, dynamic> reveal, String why) {
    final opts = (task['options'] as List?)?.cast<String>();
    String? text(Object? v) {
      if (v == null) return null;
      if (v is bool) return v ? 'True' : 'False';
      if (v is int && opts != null && v >= 0 && v < opts.length) return opts[v];
      if (v is List) return v.map(text).join(', ');
      return '$v${reveal['unit'] != null ? ' ${reveal['unit']}' : ''}';
    }
    final picked = task['kind'] == 'multi' ? text(multi.toList()..sort()) : text(answer);
    final score = (result?['score'] as num?)?.toDouble();
    context.read<AppState>().tutorContext = TutorContext(
      node: task['node'] as String?,
      taskId: task['id'] as String?,
      question: task['q'] as String,
      picked: picked,
      correct: text(reveal['answer']),
      explanation: why,
      wasRight: score == null ? null : score >= 1,
    );
    context.push('/tutor-chat');
  }

  // ---------------------------------------------------------------- medium day-X tasks

  List<Widget> _medium(Map<String, dynamic> task) {
    final reveal = result?['reveal'] as Map<String, dynamic>?;
    final chart = (task['stimulus'] as List).cast<Map<String, dynamic>>().firstWhere((s) => s['kind'] == 'chart');
    final after = reveal == null
        ? null
        : (reveal['stimulus'] as List).cast<Map<String, dynamic>>().firstWhere((s) => s['kind'] == 'chart', orElse: () => {});
    final response = task['response'] as Map<String, dynamic>;
    final horizon = response['horizon']?['label'] as String?;
    final boxes = (task['reasons']['boxes'] as List).cast<Map<String, dynamic>>();
    final pick = task['reasons']['pick'];
    final out = <Widget>[
      Text(task['brief'] as String, style: TextStyle(fontSize: 17, height: 1.4, color: kInk)),
      SizedBox(height: 12),
      _DayXChart(before: chart, after: after),
      SizedBox(height: 20),
      Text('Where did it go ${_horizonText(horizon)}?', style: TextStyle(fontWeight: FontWeight.w700)),
      SizedBox(height: 8),
      Wrap(spacing: 8, children: [
        for (final o in (response['options'] as List).cast<String>())
          ChoiceChip(
            label: Text('${_arrow(o)} ${o[0].toUpperCase()}${o.substring(1)}'),
            selected: answer == o,
            onSelected: reveal != null ? null : (_) => setState(() => answer = o),
          ),
      ]),
      SizedBox(height: 20),
      Text('Why? Pick ${pick['min']} to ${pick['max']} reasons', style: TextStyle(fontWeight: FontWeight.w700)),
      SizedBox(height: 8),
    ];
    final explained = {for (final r in (reveal?['reasons'] as List? ?? []).cast<Map<String, dynamic>>()) r['id'] as String: r};
    for (final b in boxes) {
      final id = b['id'] as String;
      final picked = reasons.contains(id);
      final r = explained[id];
      out.add(_ReasonTile(
        text: b['text'] as String,
        picked: picked,
        weight: (r?['weight'] as num?)?.toDouble(),
        explain: r?['explain'] as String?,
        onTap: reveal != null
            ? null
            : () => setState(() {
                  if (picked) {
                    reasons.remove(id);
                  } else if (reasons.length < (pick['max'] as int)) {
                    reasons.add(id);
                  }
                }),
      ));
    }
    if (reveal != null) {
      final outcome = reveal['outcome'] as Map<String, dynamic>?;
      out.insertAll(3, [
        SizedBox(height: 12),
        if (outcome != null)
          Panel(
            color: kPrimarySoft,
            border: kBorder,
            child: Text(
              'What happened: ${outcome['direction']} ${_signed(outcome['change'] as num)} ${outcome['unit'] ?? ''} '
              '${_horizonText(horizon)}. You said ${answer ?? '-'}.',
              style: TextStyle(fontWeight: FontWeight.w700, color: kInk),
            ),
          ),
      ]);
      out.add(SizedBox(height: 12));
      out.add(_ScoreBanner(
        score: (result!['score'] as num?)?.toDouble(),
        scored: true,
        note: task['variant'] == 'day_x' ? 'Day X tasks score your reasons, not the guess: nobody could know the outcome on day X.' : null,
      ));
      if (reveal['text'] != null) out.addAll([SizedBox(height: 12), TutorBubble(text: (reveal['text'] as String).trim())]);
    }
    return out;
  }

  // ---------------------------------------------------------------- summary

  Widget _summary(BuildContext context) {
    final avg = scores.isEmpty ? null : scores.reduce((a, b) => a + b) / scores.length;
    final st = lastStatus;
    final drawn = widget.run.context != 'practice';
    final passed = drawn && st != null && st[widget.run.context]?['passed'] == true;
    return Scaffold(
      appBar: AppBar(title: Text(widget.run.title), automaticallyImplyLeading: false),
      body: ListView(padding: EdgeInsets.all(24), children: [
        Center(child: MascotPlaceholder(size: 96)),
        SizedBox(height: 16),
        Text(
          completedNode ? 'Skill complete!' : drawn ? (passed ? 'Check passed' : 'Not this time') : 'Round done',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800),
        ),
        SizedBox(height: 8),
        if (avg != null)
          Text('Average score: ${(avg * 100).round()}%', textAlign: TextAlign.center, style: TextStyle(fontSize: 16, color: kBody)),
        if (earned > 0) ...[
          SizedBox(height: 12),
          Center(
            child: Container(
              padding: EdgeInsets.symmetric(horizontal: 14, vertical: 6),
              decoration: BoxDecoration(color: kPrimarySoft, borderRadius: BorderRadius.circular(999)),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                ScaleIcon(size: 20),
                SizedBox(width: 6),
                Text('+$earned Scales', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: kPrimaryText)),
              ]),
            ),
          ),
        ],
        if (st != null && !completedNode) ...[
          SizedBox(height: 16),
          Panel(
            child: Text(
              st['done'] == true
                  ? 'This skill is complete.'
                  : st['easy_done'] == true
                      ? 'The questions are done. Pass the chart task to complete the skill.'
                      : drawn && !passed
                          ? 'Every question has to be right to pass. Practise the questions instead, or try again.'
                          : 'Keep going: an 80% average on the questions finishes this part.',
              style: TextStyle(color: kBody),
            ),
          ),
        ],
        SizedBox(height: 24),
        FilledButton(
          style: FilledButton.styleFrom(minimumSize: Size.fromHeight(52)),
          onPressed: () => context.pop(),
          child: Text('Back to the skill'),
        ),
      ]),
    );
  }
}

String _fmt(num v) => v == v.roundToDouble() ? v.toInt().toString() : v.toStringAsFixed(2);
String _signed(num v) => '${v > 0 ? '+' : ''}${_fmt(v)}';
String _arrow(String o) => switch (o) { 'up' => '↑', 'down' => '↓', _ => '→' };
String _horizonText(String? h) => switch (h) {
      '1d' => 'the next day',
      '1w' => 'over the next week',
      '2w' => 'over the next two weeks',
      '1m' => 'over the next month',
      '3m' => 'over the next three months',
      '6m' => 'over the next six months',
      '1y' => 'over the next year',
      _ => 'next',
    };

// ---------------------------------------------------------------- widgets

class _OptionTile extends StatelessWidget {
  final String text;
  final bool picked;
  final bool multi;
  final bool? state; // after the reveal: true = correct, false = wrong pick, null = neutral
  final VoidCallback? onTap;
  _OptionTile({required this.text, required this.picked, this.multi = false, this.state, this.onTap});

  @override
  Widget build(BuildContext context) {
    final (bg, border) = switch (state) {
      true => (kGreenSoft, kGreen),
      false => (kRedSoft, kRed),
      null => (picked ? kPrimarySoft : kSurface, picked ? kPrimary : kLine),
    };
    return Padding(
      padding: EdgeInsets.only(bottom: 10),
      child: Material(
        color: bg,
        borderRadius: BorderRadius.circular(14),
        child: InkWell(
          borderRadius: BorderRadius.circular(14),
          onTap: onTap,
          child: Container(
            padding: EdgeInsets.all(14),
            decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), border: Border.all(color: border, width: picked ? 2 : 1)),
            child: Row(children: [
              Icon(
                state == true
                    ? Icons.check_circle
                    : state == false
                        ? Icons.cancel
                        : multi
                            ? (picked ? Icons.check_box : Icons.check_box_outline_blank)
                            : (picked ? Icons.radio_button_checked : Icons.radio_button_unchecked),
                color: state == true ? kGreen : state == false ? kRed : (picked ? kPrimaryText : kFaint),
              ),
              SizedBox(width: 10),
              Expanded(child: Text(text, style: TextStyle(fontSize: 15, color: kInk))),
            ]),
          ),
        ),
      ),
    );
  }
}

class _ReasonTile extends StatelessWidget {
  final String text;
  final bool picked;
  final double? weight; // after the reveal
  final String? explain;
  final VoidCallback? onTap;
  _ReasonTile({required this.text, required this.picked, this.weight, this.explain, this.onTap});

  @override
  Widget build(BuildContext context) {
    final revealed = weight != null;
    final tone = !revealed ? null : weight! > 0 ? kGreen : weight! < 0 ? kRed : kFaint;
    final label = !revealed ? null : weight! >= 0.7 ? 'Strong reason' : weight! > 0 ? 'Partly relevant' : weight! == 0 ? 'Not relevant' : 'Wrong or hindsight';
    return Padding(
      padding: EdgeInsets.only(bottom: 8),
      child: Material(
        color: picked ? kPrimarySoft : kSurface,
        borderRadius: BorderRadius.circular(14),
        child: InkWell(
          borderRadius: BorderRadius.circular(14),
          onTap: onTap,
          child: Container(
            padding: EdgeInsets.all(12),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: tone ?? (picked ? kPrimary : kLine), width: picked ? 2 : 1),
            ),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Icon(picked ? Icons.check_box : Icons.check_box_outline_blank, color: picked ? kPrimaryText : kFaint, size: 20),
                SizedBox(width: 10),
                Expanded(child: Text(text, style: TextStyle(color: kInk))),
              ]),
              if (revealed) ...[
                SizedBox(height: 6),
                Text(label!, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: tone)),
                if (explain != null) Text(explain!, style: TextStyle(fontSize: 13, color: kBody, height: 1.35)),
              ],
            ]),
          ),
        ),
      ),
    );
  }
}

class _ScoreBanner extends StatelessWidget {
  final double? score;
  final bool scored;
  final String? note;
  _ScoreBanner({required this.score, required this.scored, this.note});

  @override
  Widget build(BuildContext context) {
    if (!scored || score == null) {
      return Panel(color: kPrimarySoft, border: kBorder, child: Text('No right or wrong here.', style: TextStyle(color: kInk)));
    }
    final pct = (score! * 100).round();
    final good = score! >= 0.999, ok = score! >= 0.6;
    return Panel(
      color: good || ok ? kGreenSoft : kRedSoft,
      border: good || ok ? kGreen : kRed,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(good ? 'Correct · $pct%' : ok ? 'Good · $pct%' : pct > 0 ? 'Partly right · $pct%' : 'Not quite · 0%',
            style: TextStyle(fontWeight: FontWeight.w800, color: good || ok ? kGreen : kRed)),
        if (note != null) ...[SizedBox(height: 4), Text(note!, style: TextStyle(fontSize: 12, color: kBody))],
      ]),
    );
  }
}

class _ConfidencePicker extends StatelessWidget {
  final int? value;
  final ValueChanged<int> onChanged;
  _ConfidencePicker({required this.value, required this.onChanged});

  static const labels = ['Guessing', 'Unsure', 'Fairly', 'Sure', 'Certain'];

  // One line: five steps from 1 (guessing) to 5 (certain), with the words at the ends.
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          for (var i = 1; i <= 5; i++) ...[
            if (i > 1) SizedBox(width: 6),
            Expanded(
              child: Semantics(
                button: true,
                selected: value == i,
                label: '$i, ${labels[i - 1]}',
                excludeSemantics: true,
                child: InkWell(
                  key: ValueKey('confidence-$i'),
                  borderRadius: BorderRadius.circular(10),
                  onTap: () => onChanged(i),
                  child: AnimatedContainer(
                    duration: Duration(milliseconds: 150),
                    height: 44,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: value == i ? kPrimary : kSurface,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: value == i ? kPrimary : kBorder),
                    ),
                    child: Text('$i', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: value == i ? Colors.white : kInk)),
                  ),
                ),
              ),
            ),
          ],
        ]),
        SizedBox(height: 4),
        Row(children: [
          Text('Guessing', style: TextStyle(fontSize: 11, color: kMuted)),
          Spacer(),
          if (value != null) Text(labels[value! - 1], style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: kPrimaryText)),
          Spacer(),
          Text('Certain', style: TextStyle(fontSize: 11, color: kMuted)),
        ]),
      ]);
}

class _NumericInput extends StatefulWidget {
  final Map<String, dynamic> task;
  final num? value;
  final bool enabled;
  final ValueChanged<num> onChanged;
  _NumericInput({required this.task, required this.value, required this.enabled, required this.onChanged});
  @override
  State<_NumericInput> createState() => _NumericInputState();
}

class _NumericInputState extends State<_NumericInput> {
  final controller = TextEditingController();

  @override
  Widget build(BuildContext context) {
    final input = widget.task['input'] as Map<String, dynamic>?;
    final unit = widget.task['unit'] as String? ?? '';
    if (input != null) {
      final min = (input['min'] as num).toDouble(), max = (input['max'] as num).toDouble();
      final step = (input['step'] as num?)?.toDouble() ?? 1;
      final v = (widget.value ?? (min + max) / 2).toDouble().clamp(min, max);
      final divisions = ((max - min) / step).round();
      return Column(children: [
        Text('${_fmt(_snap(v, min, step))} $unit', style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800, color: kPrimaryText)),
        Slider(
          value: v,
          min: min,
          max: max,
          divisions: divisions > 0 && divisions <= 2000 ? divisions : null,
          onChanged: widget.enabled ? (x) => widget.onChanged(_snap(x, min, step)) : null,
          onChangeStart: widget.enabled ? (x) => widget.onChanged(_snap(x, min, step)) : null,
        ),
        Row(children: [
          Text('${_fmt(min)} $unit', style: TextStyle(fontSize: 12, color: kMuted)),
          Spacer(),
          Text('${_fmt(max)} $unit', style: TextStyle(fontSize: 12, color: kMuted)),
        ]),
        if (widget.value == null) Text('Move the slider to answer', style: TextStyle(fontSize: 12, color: kMuted)),
      ]);
    }
    return TextField(
      controller: controller,
      enabled: widget.enabled,
      keyboardType: TextInputType.numberWithOptions(decimal: true, signed: true),
      decoration: InputDecoration(suffixText: unit, border: OutlineInputBorder(borderRadius: BorderRadius.circular(12))),
      onChanged: (t) {
        final v = num.tryParse(t.replaceAll(',', '.').replaceAll(' ', ''));
        if (v != null) widget.onChanged(v);
      },
    );
  }

  num _snap(double x, double min, double step) {
    final snapped = min + ((x - min) / step).round() * step;
    return double.parse(snapped.toStringAsFixed(6));
  }
}

/// Line chart up to day X; after the reveal, the line continues in a second colour.
class _DayXChart extends StatelessWidget {
  final Map<String, dynamic> before;
  final Map<String, dynamic>? after;
  _DayXChart({required this.before, this.after});

  List<FlSpot> _spots(Map<String, dynamic>? chart) {
    final series = (chart?['series'] as List?)?.cast<Map<String, dynamic>>();
    if (series == null || series.isEmpty) return [];
    return [for (final p in (series.first['points'] as List)) FlSpot((p['t'] as num).toDouble(), (p['v'] as num).toDouble())];
  }

  @override
  Widget build(BuildContext context) {
    final series = (before['series'] as List).cast<Map<String, dynamic>>();
    final first = series.first;
    final past = _spots(before);
    final next = _spots(after);
    final attribution = (before['attribution'] as List? ?? []);
    return Panel(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text('${first['label']} · ${first['unit']}', style: TextStyle(fontWeight: FontWeight.w700, color: kInk))),
          if (before['synthetic'] == true)
            Container(
              padding: EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(color: kWarnSoft, borderRadius: BorderRadius.circular(8), border: Border.all(color: kWarnBorder)),
              child: Text('Synthetic data', style: TextStyle(fontSize: 11, color: kWarnText, fontWeight: FontWeight.w700)),
            ),
        ]),
        SizedBox(height: 12),
        SizedBox(
          height: 200,
          child: LineChart(LineChartData(
            gridData: FlGridData(show: true, drawVerticalLine: false, getDrawingHorizontalLine: (_) => FlLine(color: kLine, strokeWidth: 1)),
            borderData: FlBorderData(show: false),
            maxX: next.isEmpty ? (past.isEmpty ? 0 : past.last.x + 5) : next.last.x,
            titlesData: FlTitlesData(
              rightTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
              topTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
              bottomTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
              leftTitles: AxisTitles(sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 44,
                getTitlesWidget: (v, meta) => Text(meta.formattedValue, style: TextStyle(fontSize: 10, color: kMuted)),
              )),
            ),
            extraLinesData: ExtraLinesData(verticalLines: [
              VerticalLine(
                x: 0,
                color: kWarnIcon,
                strokeWidth: 1.5,
                dashArray: [4, 4],
                label: VerticalLineLabel(
                  show: true,
                  alignment: Alignment.topLeft,
                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: kWarnText),
                  labelResolver: (_) => 'Day X',
                ),
              ),
            ]),
            lineBarsData: [
              LineChartBarData(spots: past, color: kPrimary, barWidth: 2.5, dotData: FlDotData(show: false)),
              if (next.isNotEmpty) LineChartBarData(spots: next, color: kWarnIcon, barWidth: 2.5, dotData: FlDotData(show: false)),
            ],
          )),
        ),
        SizedBox(height: 6),
        Text(next.isEmpty ? 'The chart stops on day X. What came next is hidden until you answer.' : 'Orange: what happened after day X.',
            style: TextStyle(fontSize: 11, color: kMuted)),
        for (final a in attribution)
          Text('Source: ${a['source']} (${a['licence']})', style: TextStyle(fontSize: 11, color: kMuted)),
      ]),
    );
  }
}
