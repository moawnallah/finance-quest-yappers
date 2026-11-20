// Tutor chat. OFFLINE DEMO: answers come from our own reviewed explanations
// (roadmap.json "why" texts) by keyword match. The live version will call a
// serverless /api/tutor (Gemini or Claude) with the same guardrails:
// explain, never recommend products, Polish context, clearly labelled as AI.

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../widgets/common.dart';

class TutorScreen extends StatefulWidget {
  TutorScreen({super.key});
  @override
  State<TutorScreen> createState() => _TutorScreenState();
}

class _TutorScreenState extends State<TutorScreen> {
  final ctrl = TextEditingController();
  final msgs = <(bool, String)>[
    (false, 'Hi! Ask me about any investing idea, for example "what is diversification?" or "what is an ETF?". I explain concepts; I do not tell you what to buy.'),
  ];

  static final _adviceWords = RegExp(r'\b(should i (buy|sell)|buy|sell|which (stock|etf|fund)|recommend|will .* (go up|rise|fall))\b', caseSensitive: false);

  String _answer(String text, AppState s) {
    if (_adviceWords.hasMatch(text)) {
      return 'I can\'t tell you what to buy or sell, or predict prices. What I can do: explain how to judge a choice yourself, for example risk, fees, '
          'diversification and how your ${s.profile.horizonYears}-year horizon changes things. Want me to explain one of those?';
    }
    final words = text.toLowerCase().split(RegExp(r'[^a-ząćęłńóśźż0-9]+')).where((w) => w.length > 3).toSet();
    var best = (0, '');
    for (final sl in s.roadmap?.slices ?? []) {
      for (final n in sl.nodes) {
        for (final q in n.questions) {
          if (q.why == null) continue;
          final hay = '${q.q} ${q.why} ${n.title} ${sl.label}'.toLowerCase();
          final score = words.where(hay.contains).length;
          if (score > best.$1) best = (score, '${q.why} (from "${n.title}" in ${sl.label})');
        }
      }
    }
    return best.$1 == 0
        ? 'I don\'t have that in my lessons yet. Try asking about shares, bonds, ETFs, inflation, fees or diversification.'
        : best.$2;
  }

  void _send(AppState s) {
    final t = ctrl.text.trim();
    if (t.isEmpty) return;
    setState(() {
      msgs.add((true, t));
      msgs.add((false, _answer(t, s)));
      ctrl.clear();
    });
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    return Scaffold(
      appBar: AppBar(
        title: Text('Tutor'),
        bottom: PreferredSize(
          preferredSize: Size.fromHeight(24),
          child: Padding(
            padding: EdgeInsets.only(bottom: 8),
            child: Text('Offline demo · AI version coming · educational, not advice', style: TextStyle(fontSize: 12, color: kMuted)),
          ),
        ),
      ),
      body: Column(children: [
        Expanded(
          child: ListView(padding: EdgeInsets.all(16), children: [
            for (final (mine, text) in msgs)
              Align(
                alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
                child: Container(
                  margin: EdgeInsets.only(bottom: 10),
                  padding: EdgeInsets.all(12),
                  constraints: BoxConstraints(maxWidth: 340),
                  decoration: BoxDecoration(
                    color: mine ? kPrimary : kSurface,
                    borderRadius: BorderRadius.circular(14),
                    border: mine ? null : Border.all(color: kTutorBorder),
                  ),
                  child: Text(text, style: TextStyle(color: mine ? Colors.white : kInk, height: 1.4)),
                ),
              ),
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
                  decoration: InputDecoration(hintText: 'Ask something...', border: OutlineInputBorder()),
                  onSubmitted: (_) => _send(s),
                ),
              ),
              SizedBox(width: 8),
              IconButton.filled(onPressed: () => _send(s), icon: Icon(Icons.send), tooltip: 'Send'),
            ]),
          ),
        ),
      ]),
    );
  }
}
