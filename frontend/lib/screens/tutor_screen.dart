// Tutor chat. Opened from the Tutor tab, or from a question ("Ask the tutor
// about this"), in which case it starts from that question: what was asked,
// what the user picked, the right answer and the explanation.
//
// Answers come from the backend's POST /tutor (Mateusz's tutor agent with its
// guardrails) when it is available. Until then, the app answers from the
// stored, human-written explanation and lesson cards, in a conversational way.
// It never recommends products or predicts prices.

import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../data/mermaid.dart';
import '../widgets/common.dart';

class TutorScreen extends StatefulWidget {
  final bool fromQuestion;
  TutorScreen({super.key, this.fromQuestion = false});
  @override
  State<TutorScreen> createState() => _TutorScreenState();
}

class _Msg {
  final bool mine;
  final String text;
  Uint8List? image; // a rendered chart or diagram (never raw Mermaid code)
  bool drawing = false;
  _Msg(this.mine, this.text);
}

class _TutorScreenState extends State<TutorScreen> {
  final ctrl = TextEditingController();
  final scroll = ScrollController();
  final msgs = <_Msg>[];
  TutorContext? ctx;
  bool typing = false;
  String? example; // a lesson-card example for this skill, loaded once

  static final _adviceWords = RegExp(
      r'\b(should i (buy|sell)|buy|sell|which (stock|share|etf|fund)|recommend|will .* (go up|rise|fall)|best (stock|fund|etf))\b',
      caseSensitive: false);

  @override
  void initState() {
    super.initState();
    final s = context.read<AppState>();
    ctx = widget.fromQuestion ? s.tutorContext : null;
    if (ctx == null) {
      msgs.add(_Msg(false, 'Hi! Ask me about any investing idea, for example "what is diversification?" or "what is an ETF?". I explain ideas; I never tell you what to buy.'));
    } else {
      final c = ctx!;
      final opener = c.wasRight == true
          ? 'Nice, you got this one right. ${c.explanation ?? ''}'
          : c.picked != null && c.correct != null
              ? 'Let\'s look at this one together. You picked "${c.picked}", and the answer is "${c.correct}". ${c.explanation ?? ''}'
              : c.explanation ?? 'Let\'s look at this question together.';
      msgs.add(_Msg(false, '${opener.trim()}\n\nWhat would you like to know?'));
      if (c.node != null) {
        s.api.skill(s.profile.name, c.node!).then((d) {
          final cards = ((d['node'] as Map)['cards'] as List).cast<Map>();
          final ex = cards.map((x) => x['example']).whereType<String>().firstOrNull;
          if (mounted) setState(() => example = ex);
        }).catchError((_) {});
      }
    }
  }

  @override
  void dispose() {
    ctrl.dispose();
    scroll.dispose();
    super.dispose();
  }

  List<String> get _suggestions => ctx == null
      ? ['What is diversification?', 'Draw compound growth as a line chart', 'What does inflation do to my savings?']
      : [
          if (ctx!.wasRight != true) 'Why was my answer wrong?',
          'Explain it more simply',
          'Give me an example',
          'How does this fit my goal?',
          'Show it as a chart',
        ];

  // Offline answer from the stored explanation and lesson cards.
  String _offline(String text, AppState s) {
    final t = text.toLowerCase();
    if (_adviceWords.hasMatch(text)) {
      return 'I can\'t tell you what to buy or sell, or predict prices. What I can do is help you judge a choice yourself: '
          'risk, costs, spreading your money, and how your ${s.profile.horizonYears}-year horizon changes things. Which one should we look at?';
    }
    final c = ctx;
    if (c != null) {
      final why = c.explanation ?? '';
      // the explanation continues a sentence here, so start it in lower case
      final whyMid = why.isEmpty ? why : why[0].toLowerCase() + why.substring(1);
      if (t.contains('wrong') || t.contains('why')) {
        if (c.wasRight == true) return 'You weren\'t wrong here. The reason it works: $why';
        return 'The question was: "${c.question}". "${c.picked ?? 'Your answer'}" doesn\'t fit because $whyMid '
            '${c.correct != null ? 'That is why the answer is "${c.correct}".' : ''}'.trim();
      }
      if (t.contains('simpl') || t.contains('easier') || t.contains('plain')) {
        final first = why.split(RegExp(r'(?<=[.!?])\s')).first;
        return 'In one line: $first${c.correct != null ? ' So the answer is "${c.correct}".' : ''}';
      }
      if (t.contains('example')) {
        return example != null ? 'Here is a real example: $example' : 'Think of a real case: $why Try picturing it with your own monthly budget.';
      }
      if (t.contains('goal') || t.contains('me ') || t.endsWith('me')) {
        return 'Your goal is ${s.profile.goal.toLowerCase()} in ${s.profile.horizonYears} years. $why '
            'Keep this in mind when you compare options for that goal, and ask yourself how a bad year would feel.';
      }
    }
    // Free question: find the closest stored explanation.
    final words = t.split(RegExp(r'[^a-ząćęłńóśźż0-9]+')).where((w) => w.length > 3).toSet();
    var best = (0, '');
    for (final sl in s.roadmap?.slices ?? []) {
      for (final n in sl.nodes) {
        for (final q in n.questions) {
          if (q.why == null) continue;
          final hay = '${q.q} ${q.why} ${n.title}'.toLowerCase();
          final score = words.where(hay.contains).length;
          if (score > best.$1) best = (score, q.why!);
        }
      }
    }
    if (best.$1 > 0) return best.$2;
    return c != null
        ? 'Good question. Here is the key idea again: ${c.explanation ?? ''} Want me to explain it more simply or give an example?'
        : 'I don\'t have that in my lessons yet. Try asking about shares, bonds, ETFs, inflation, costs or spreading your money.';
  }

  Future<void> _send(String text) async {
    final t = text.trim();
    if (t.isEmpty || typing) return;
    final s = context.read<AppState>();
    setState(() {
      msgs.add(_Msg(true, t));
      ctrl.clear();
      typing = true;
    });
    _toEnd();
    String reply;
    String? diagram;
    try {
      final r = await s.api.tutor(
        s.profile.name,
        mode: ctx == null ? 'explain_concept' : (ctx!.wasRight == true ? 'explain_concept' : 'explain_result'),
        message: t,
        context: ctx?.toJson(),
        history: [for (final m in msgs) {'role': m.mine ? 'user' : 'tutor', 'text': m.text}],
      );
      reply = r.text;
      diagram = r.mermaid;
    } catch (_) {
      await Future.delayed(Duration(milliseconds: 450)); // a short "typing" beat
      reply = _offline(t, s);
    }
    if (!mounted) return;
    final msg = _Msg(false, reply);
    setState(() {
      msgs.add(msg);
      typing = false;
    });
    _toEnd();
    if (diagram != null) await _draw(msg, diagram, t);
  }

  /// Check and render the tutor's diagram before showing it. If Mermaid rejects
  /// the code, send the error back to the tutor for a fix (two tries), so the
  /// learner only ever sees a finished picture, never broken code.
  Future<void> _draw(_Msg msg, String code, String request) async {
    if (!mermaidSupported) return;
    final s = context.read<AppState>();
    setState(() => msg.drawing = true);
    var current = code;
    for (var attempt = 0; attempt < 3; attempt++) {
      try {
        final png = await renderMermaid(current, dark: appDark);
        if (!mounted) return;
        setState(() {
          msg.image = png;
          msg.drawing = false;
        });
        _toEnd();
        return;
      } catch (e) {
        if (attempt == 2) break;
        try {
          final fixed = await s.api.tutor(s.profile.name,
              mode: 'repair_diagram', message: '$e', context: {...?ctx?.toJson(), 'mermaid': current, 'request': request});
          if (fixed.mermaid == null) break;
          current = fixed.mermaid!;
        } catch (_) {
          break;
        }
      }
    }
    if (mounted) setState(() => msg.drawing = false);
  }

  void _toEnd() => WidgetsBinding.instance.addPostFrameCallback((_) {
        if (scroll.hasClients) scroll.animateTo(scroll.position.maxScrollExtent, duration: Duration(milliseconds: 250), curve: Curves.easeOut);
      });

  @override
  Widget build(BuildContext context) {
    final c = ctx;
    return Scaffold(
      appBar: widget.fromQuestion ? AppBar(title: Text('Ask the tutor')) : StatsBar(title: 'Tutor'),
      body: Column(children: [
        Expanded(
          child: ListView(controller: scroll, padding: EdgeInsets.all(16), children: [
            if (c != null)
              Container(
                margin: EdgeInsets.only(bottom: 14),
                padding: EdgeInsets.all(12),
                decoration: BoxDecoration(color: kPrimarySoft, borderRadius: BorderRadius.circular(14)),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('ABOUT THIS QUESTION', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: .6, color: kPrimaryText)),
                  SizedBox(height: 4),
                  Text(c.question, style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
                  if (c.picked != null) ...[
                    SizedBox(height: 6),
                    Row(children: [
                      Icon(c.wasRight == true ? Icons.check_circle : Icons.cancel, size: 16, color: c.wasRight == true ? kGreen : kRed),
                      SizedBox(width: 6),
                      Expanded(child: Text('You picked: ${c.picked}', style: TextStyle(color: kBody))),
                    ]),
                  ],
                  if (c.correct != null && c.wasRight != true) ...[
                    SizedBox(height: 4),
                    Row(children: [
                      Icon(Icons.check_circle, size: 16, color: kGreen),
                      SizedBox(width: 6),
                      Expanded(child: Text('Answer: ${c.correct}', style: TextStyle(color: kBody))),
                    ]),
                  ],
                ]),
              ),
            for (final m in msgs) _bubble(m),
            if (typing) _bubble(_Msg(false, '...')),
          ]),
        ),
        SizedBox(
          height: 44,
          child: ListView(scrollDirection: Axis.horizontal, padding: EdgeInsets.symmetric(horizontal: 12), children: [
            for (final q in _suggestions)
              Padding(padding: EdgeInsets.only(right: 8), child: ActionChip(label: Text(q), onPressed: typing ? null : () => _send(q))),
          ]),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: EdgeInsets.fromLTRB(12, 4, 12, 8),
            child: Row(children: [
              Expanded(
                child: TextField(
                  controller: ctrl,
                  decoration: InputDecoration(
                    hintText: c == null ? 'Ask something...' : 'Ask about this question...',
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
                    isDense: true,
                  ),
                  onSubmitted: _send,
                ),
              ),
              SizedBox(width: 8),
              IconButton.filled(onPressed: typing ? null : () => _send(ctrl.text), icon: Icon(Icons.send), tooltip: 'Send'),
            ]),
          ),
        ),
      ]),
    );
  }

  Widget _bubble(_Msg m) => Align(
        alignment: m.mine ? Alignment.centerRight : Alignment.centerLeft,
        child: Row(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.end, children: [
          if (!m.mine) ...[MascotPlaceholder(size: 28), SizedBox(width: 6)],
          Flexible(
            child: Container(
              margin: EdgeInsets.only(bottom: 10),
              padding: EdgeInsets.all(12),
              constraints: BoxConstraints(maxWidth: 420),
              decoration: BoxDecoration(
                color: m.mine ? kPrimary : kSurface,
                borderRadius: BorderRadius.only(
                  topLeft: Radius.circular(14), topRight: Radius.circular(14),
                  bottomLeft: Radius.circular(m.mine ? 14 : 4), bottomRight: Radius.circular(m.mine ? 4 : 14),
                ),
                border: m.mine ? null : Border.all(color: kTutorBorder),
              ),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                Text(m.text, style: TextStyle(color: m.mine ? Colors.white : kInk, height: 1.4)),
                if (m.drawing) ...[
                  SizedBox(height: 10),
                  Row(mainAxisSize: MainAxisSize.min, children: [
                    SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: kPrimary)),
                    SizedBox(width: 8),
                    Text('Drawing the chart...', style: TextStyle(fontSize: 12, color: kMuted)),
                  ]),
                ],
                if (m.image != null) ...[
                  SizedBox(height: 10),
                  ClipRRect(borderRadius: BorderRadius.circular(10), child: Image.memory(m.image!, fit: BoxFit.contain, filterQuality: FilterQuality.medium)),
                ],
              ]),
            ),
          ),
        ]),
      );
}
