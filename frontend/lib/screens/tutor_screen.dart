// Tutor chat with a conversation list. On wide screens the conversations sit
// in a panel on the left; on phones they open from a "Conversations" button.
// Opened from a question ("Ask the tutor about this"), it starts a new
// conversation that knows the question, the answer picked, the right answer
// and the explanation.
//
// Answers come from the backend's POST /tutor (Mateusz's tutor agent with its
// guardrails) when it is available; otherwise from the stored, human-written
// explanations. Charts and diagrams are rendered from validated Mermaid code,
// never shown as raw code. The tutor never recommends products or predicts prices.

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../data/api.dart' show ApiException;
import '../data/app_state.dart';
import '../data/mermaid.dart';
import '../data/stream.dart';
import '../widgets/common.dart';

class TutorScreen extends StatefulWidget {
  final bool fromQuestion;
  TutorScreen({super.key, this.fromQuestion = false});
  @override
  State<TutorScreen> createState() => _TutorScreenState();
}

class _TutorScreenState extends State<TutorScreen> {
  final ctrl = TextEditingController();
  final scroll = ScrollController();
  bool typing = false;
  final Map<String, String> _examples = {}; // node -> lesson-card example

  static final _adviceWords = RegExp(
      r'\b(should i (buy|sell)|buy|sell|which (stock|share|etf|fund)|recommend|will .* (go up|rise|fall)|best (stock|fund|etf))\b',
      caseSensitive: false);

  @override
  void initState() {
    super.initState();
    final s = context.read<AppState>();
    if (widget.fromQuestion && s.tutorContext != null) {
      _start(s, s.tutorContext);
      s.tutorContext = null;
    } else if (s.currentConversation == null) {
      if (s.conversationsLoaded) {
        _start(s, null);
      } else {
        s.loadConversations().then((_) {
          if (mounted && s.currentConversation == null) setState(() => _start(s, null));
        });
      }
    }
  }

  @override
  void dispose() {
    ctrl.dispose();
    scroll.dispose();
    super.dispose();
  }

  /// A new conversation with its opening message.
  void _start(AppState s, TutorContext? c) {
    final conv = s.newConversation(context: c);
    if (conv.messages.isNotEmpty) return; // reused an empty chat that already has its greeting
    if (c == null) {
      conv.messages.add(TutorMessage(false, 'Hi! Ask me about any investing idea, for example "what is diversification?", or ask me to draw a chart. I explain ideas; I never tell you what to buy.'));
      return;
    }
    final opener = c.wasRight == true
        ? 'Nice, you got this one right. ${c.explanation ?? ''}'
        : c.picked != null && c.correct != null
            ? 'Let\'s look at this one together. You picked "${c.picked}", and the answer is "${c.correct}". ${c.explanation ?? ''}'
            : c.explanation ?? 'Let\'s look at this question together.';
    conv.messages.add(TutorMessage(false, '${opener.trim()}\n\nWhat would you like to know?'));
    final node = c.node;
    if (node != null && !_examples.containsKey(node)) {
      s.api.skill(s.profile.name, node).then((d) {
        final cards = ((d['node'] as Map)['cards'] as List).cast<Map>();
        final ex = cards.map((x) => x['example']).whereType<String>().firstOrNull;
        if (ex != null && mounted) setState(() => _examples[node] = ex);
      }).catchError((_) {});
    }
  }

  List<String> _suggestions(TutorConversation conv) => conv.context == null
      ? ['What is diversification?', 'Draw compound growth as a line chart', 'What does inflation do to my savings?']
      : [
          if (conv.context!.wasRight != true) 'Why was my answer wrong?',
          'Explain it more simply',
          'Give me an example',
          'How does this fit my goal?',
          'Show it as a chart',
        ];

  // Offline answer from the stored explanation and lesson cards.
  String _offline(String text, AppState s, TutorContext? c) {
    final t = text.toLowerCase();
    if (_adviceWords.hasMatch(text)) {
      return 'I can\'t tell you what to buy or sell, or predict prices. What I can do is help you judge a choice yourself: '
          'risk, costs, spreading your money, and how your ${s.profile.horizonYears}-year horizon changes things. Which one should we look at?';
    }
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
        final ex = c.node == null ? null : _examples[c.node];
        return ex != null ? 'Here is a real example: $ex' : 'Think of a real case: $why Try picturing it with your own monthly budget.';
      }
      if (t.contains('goal')) {
        return 'Your goal is ${s.profile.goal.toLowerCase()} in ${s.profile.horizonYears} years. $why '
            'Keep this in mind when you compare options for that goal, and ask yourself how a bad year would feel.';
      }
    }
    if (RegExp(r'\b(chart|graph|plot|diagram|draw)\b').hasMatch(t)) {
      return 'I can draw charts once the live tutor is connected. Meanwhile, ask me to explain the idea in words.';
    }
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
    final s = context.read<AppState>();
    final conv = s.currentConversation;
    if (t.isEmpty || typing || conv == null) return;
    setState(() {
      conv.messages.add(TutorMessage(true, t));
      if (!conv.titled && conv.context == null) conv.title = _quickTitle(t);
      ctrl.clear();
      typing = true;
    });
    _toEnd();
    String reply;
    String? diagram;
    final mode = conv.context == null || conv.context!.wasRight == true ? 'explain_concept' : 'explain_result';
    // Earlier turns only: the new question is sent separately as `message`.
    final history = [for (final m in conv.messages.take(conv.messages.length - 1)) {'role': m.mine ? 'user' : 'tutor', 'text': m.text}];
    // The reply bubble appears with the first streamed words and grows as the model writes.
    TutorMessage? live;
    try {
      if (!streamSupported) throw UnsupportedError('no streaming');
      final r = await s.api.tutorStream(s.profile.name, mode: mode, message: t, context: conv.context?.toJson(), history: history,
          onDelta: (d) {
        if (!mounted) return;
        setState(() {
          if (live == null) {
            live = TutorMessage(false, '');
            conv.messages.add(live!);
            typing = false;
          }
          live!.text += d;
        });
        _toEnd();
      });
      reply = r.text;
      diagram = r.mermaid;
    } catch (e) {
      try {
        if (e is ApiException && e.status == 503) rethrow; // model down: go straight to the lesson-based answer
        final r = await s.api.tutor(s.profile.name, mode: mode, message: t, context: conv.context?.toJson(), history: history);
        reply = r.text;
        diagram = r.mermaid;
      } catch (_) {
        await Future.delayed(Duration(milliseconds: 450)); // a short "typing" beat
        reply = _offline(t, s, conv.context);
      }
    }
    if (!mounted) return;
    final msg = live ?? TutorMessage(false, reply);
    setState(() {
      msg.text = reply; // the final, checked text
      if (live == null) conv.messages.add(msg);
      typing = false;
    });
    s.notify(); // the list's preview updates
    s.saveConversations();
    _toEnd();
    if (!conv.titled) _autoTitle(conv, t, reply);
    if (diagram != null) await _draw(conv, msg, diagram, t);
  }

  /// A readable title from the first question, until the model writes one.
  String _quickTitle(String t) {
    final words = t.replaceAll(RegExp(r'[?!.]+$'), '').split(RegExp(r'\s+')).where((w) => w.isNotEmpty).take(6).join(' ');
    return words.isEmpty ? 'New chat' : words[0].toUpperCase() + words.substring(1);
  }

  /// Ask the tutor model for a short title after the first exchange.
  Future<void> _autoTitle(TutorConversation conv, String question, String answer) async {
    final s = context.read<AppState>();
    try {
      final r = await s.api.tutor(s.profile.name, mode: 'title', message: 'Learner: $question\nTutor: $answer');
      const q = '"\'';  // both quote characters
      final title = r.text.trim().replaceAll(RegExp('^[$q]+|[$q.]+\$'), '');
      if (title.isNotEmpty && title.length <= 60 && !conv.titled) s.renameConversation(conv.id, title);
    } catch (_) {
      // offline: keep the title from the question
    }
  }

  Future<void> _rename(AppState s, TutorConversation c) async {
    final ctrl = TextEditingController(text: c.title);
    final title = await showDialog<String>(
      context: context,
      builder: (d) => AlertDialog(
        title: Text('Rename conversation'),
        content: TextField(controller: ctrl, autofocus: true, maxLength: 60, onSubmitted: (v) => Navigator.pop(d, v)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(d), child: Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(d, ctrl.text), child: Text('Save')),
        ],
      ),
    );
    if (title != null) s.renameConversation(c.id, title);
  }

  /// Check and render the tutor's diagram before showing it. If Mermaid rejects
  /// the code, send the error back for a fix (two tries); the learner only sees
  /// a finished picture, never broken code.
  Future<void> _draw(TutorConversation conv, TutorMessage msg, String code, String request) async {
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
              mode: 'repair_diagram', message: '$e', context: {...?conv.context?.toJson(), 'mermaid': current, 'request': request});
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

  // ---------------------------------------------------------------- conversation list

  Widget _list(AppState s, {VoidCallback? onPicked}) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Padding(
          padding: EdgeInsets.fromLTRB(12, 12, 12, 8),
          child: FilledButton.icon(
            icon: Icon(Icons.add),
            label: Text('New chat'),
            onPressed: () {
              setState(() => _start(s, null));
              onPicked?.call();
            },
          ),
        ),
        Padding(
          padding: EdgeInsets.fromLTRB(16, 4, 16, 6),
          child: Text('Conversations', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800, letterSpacing: .4, color: kMuted)),
        ),
        Expanded(
          child: ListView(padding: EdgeInsets.symmetric(horizontal: 8), children: [
            for (final c in s.conversations)
              Padding(
                padding: EdgeInsets.only(bottom: 4),
                child: Material(
                  color: c.id == s.activeConversation ? kPrimarySoft : Colors.transparent,
                  borderRadius: BorderRadius.circular(10),
                  child: ListTile(
                    dense: true,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    leading: Icon(c.context != null ? Icons.quiz_outlined : Icons.chat_bubble_outline, size: 18,
                        color: c.id == s.activeConversation ? kPrimaryText : kMuted),
                    title: Text(c.title, maxLines: 1, overflow: TextOverflow.ellipsis,
                        style: TextStyle(fontWeight: c.id == s.activeConversation ? FontWeight.w700 : FontWeight.w500, color: kInk)),
                    subtitle: Text(
                      c.messages.isEmpty ? '' : c.messages.last.text.replaceAll('\n', ' '),
                      maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 11, color: kMuted),
                    ),
                    trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                      IconButton(
                        tooltip: 'Rename conversation',
                        visualDensity: VisualDensity.compact,
                        icon: Icon(Icons.edit_outlined, size: 16, color: kFaint),
                        onPressed: () => _rename(s, c),
                      ),
                      IconButton(
                        tooltip: 'Delete conversation',
                        visualDensity: VisualDensity.compact,
                        icon: Icon(Icons.close, size: 16, color: kFaint),
                        onPressed: () => setState(() {
                          s.deleteConversation(c.id);
                          if (s.currentConversation == null) _start(s, null);
                        }),
                      ),
                    ]),
                    onTap: () {
                      s.openConversation(c.id);
                      onPicked?.call();
                      _toEnd();
                    },
                  ),
                ),
              ),
          ]),
        ),
      ]);

  void _openListSheet(AppState s) => showModalBottomSheet(
        context: context,
        backgroundColor: Colors.transparent,
        isScrollControlled: true,
        builder: (ctx) => Consumer<AppState>(
          builder: (ctx, s, _) => Container(
            height: MediaQuery.sizeOf(ctx).height * 0.6,
            decoration: BoxDecoration(color: kBg, borderRadius: BorderRadius.vertical(top: Radius.circular(24))),
            child: SafeArea(child: _list(s, onPicked: () => Navigator.pop(ctx))),
          ),
        ),
      );

  // ---------------------------------------------------------------- chat

  Widget _chat(AppState s, TutorConversation conv, {required bool wide}) {
    final c = conv.context;
    return Column(children: [
      if (!wide)
        Padding(
          padding: EdgeInsets.fromLTRB(8, 0, 8, 0),
          child: Row(children: [
            TextButton.icon(
              icon: Icon(Icons.forum_outlined, size: 18),
              label: Text('Conversations (${s.conversations.length})'),
              onPressed: () => _openListSheet(s),
            ),
            Spacer(),
            TextButton.icon(icon: Icon(Icons.add, size: 18), label: Text('New chat'), onPressed: () => setState(() => _start(s, null))),
          ]),
        ),
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
          for (final m in conv.messages) _bubble(m),
          if (typing) _bubble(TutorMessage(false, '...')),
        ]),
      ),
      SizedBox(
        height: 44,
        child: ListView(scrollDirection: Axis.horizontal, padding: EdgeInsets.symmetric(horizontal: 12), children: [
          for (final q in _suggestions(conv))
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
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final conv = s.currentConversation;
    final wide = isWideWeb(context);
    final appBar = widget.fromQuestion ? AppBar(title: Text('Ask the tutor')) : StatsBar(title: 'Tutor');
    if (conv == null) return Scaffold(appBar: appBar, body: SizedBox());
    return Scaffold(
      appBar: appBar as PreferredSizeWidget,
      body: wide
          ? Row(children: [
              Container(
                width: 280,
                decoration: BoxDecoration(border: Border(right: BorderSide(color: kLine))),
                child: _list(s),
              ),
              Expanded(child: _chat(s, conv, wide: true)),
            ])
          : _chat(s, conv, wide: false),
    );
  }

  Widget _bubble(TutorMessage m) => Align(
        alignment: m.mine ? Alignment.centerRight : Alignment.centerLeft,
        child: Row(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.end, children: [
          if (!m.mine) ...[MascotPlaceholder(size: 28), SizedBox(width: 6)],
          Flexible(
            child: Container(
              margin: EdgeInsets.only(bottom: 10),
              padding: EdgeInsets.all(12),
              constraints: BoxConstraints(maxWidth: 520),
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
