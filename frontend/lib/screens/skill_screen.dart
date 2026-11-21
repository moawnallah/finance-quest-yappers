// One skills-tree node (GET /skills/{id}): progress, lesson cards with sources, and the ways in:
// practise the questions, the chart task (medium), the prerequisite test or the test-out.

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../widgets/common.dart';
import 'skills_screen.dart' show ErrorPanel, panelName;
import 'task_screen.dart';
import 'steps_screen.dart';

class SkillScreen extends StatefulWidget {
  final String nodeId;
  SkillScreen({super.key, required this.nodeId});
  @override
  State<SkillScreen> createState() => _SkillScreenState();
}

class _SkillScreenState extends State<SkillScreen> {
  late Future<Map<String, dynamic>> future;
  Map<String, dynamic>? stepsTask; // draft "build your plan" block task, if this skill has one

  @override
  void initState() {
    super.initState();
    future = _load();
    loadStepsTask(widget.nodeId).then((t) {
      if (mounted) setState(() => stepsTask = t);
    });
  }

  Future<void> _plan() async {
    if (stepsTask == null) return;
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => StepsScreen(task: stepsTask!)));
  }

  /// The mission: the questions, then the chart task, then "build your plan".
  /// Resumes after the last finished question; starts over once all are done.
  Future<void> _startMission(String title, List<String> ids) async {
    final done = context.read<AppState>().answeredInMission[widget.nodeId] ?? {};
    final left = [for (final i in ids) if (!done.contains(i)) i];
    final run = left.isEmpty || left.length == ids.length
        ? TaskRun(title: title, taskIds: ids, skill: widget.nodeId)
        : TaskRun(title: title, taskIds: left, skill: widget.nodeId, doneBefore: ids.length - left.length);
    if (left.isEmpty) context.read<AppState>().answeredInMission.remove(widget.nodeId);
    if (ids.isNotEmpty) await context.push('/skill-run', extra: run);
    if (!mounted) return;
    await _plan();
    _reload();
  }

  Future<Map<String, dynamic>> _load() {
    final s = context.read<AppState>();
    return s.api.skill(s.profile.name, widget.nodeId);
  }

  void _reload() => setState(() => future = _load());

  Future<void> _run(TaskRun run) async {
    await context.push('/skill-run', extra: run);
    _reload();
  }

  Future<void> _drawn(String path, String context, String title) async {
    final s = this.context.read<AppState>();
    try {
      final test = await s.api.drawnTest(s.profile.name, widget.nodeId, path);
      final ids = [for (final i in test['items'] as List) i['id'] as String];
      if (ids.isEmpty) {
        if (mounted) ScaffoldMessenger.of(this.context).showSnackBar(SnackBar(content: Text('No questions to draw for this skill yet.')));
        return;
      }
      await _run(TaskRun(title: title, taskIds: ids, context: context, forNode: widget.nodeId));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(this.context).showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Mission')),
      body: FutureBuilder<Map<String, dynamic>>(
        future: future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done && !snap.hasData) return Center(child: CircularProgressIndicator());
          if (snap.hasError) return ErrorPanel(message: '${snap.error}', onRetry: _reload);
          final node = snap.data!['node'] as Map<String, dynamic>;
          final medium = (snap.data!['medium'] as List).cast<Map<String, dynamic>>();
          final st = snap.data!['status'] as Map<String, dynamic>;
          final items = (node['items'] as List).cast<Map<String, dynamic>>();
          final cards = (node['cards'] as List).cast<Map<String, dynamic>>();
          final title = node['title'] as String;
          return ListView(padding: EdgeInsets.fromLTRB(20, 8, 20, 32), children: [
            Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(panelName(node['panel'] as String).toUpperCase(),
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, letterSpacing: .6, color: kPrimaryText)),
                SizedBox(height: 4),
                Text(title, style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800, height: 1.2)),
              ])),
              MascotPlaceholder(size: 150, pose: st['done'] == true ? 'cheer' : 'point', headOnPhone: true),
            ]),
            SizedBox(height: 16),
            _StatusPanel(status: st, hasMedium: medium.isNotEmpty),
            SizedBox(height: 14),
            FilledButton.icon(
              icon: Icon(st['done'] == true ? Icons.replay : Icons.play_arrow_rounded),
              label: Builder(builder: (context) {
                final ids = [for (final i in items) i['id'] as String, for (final t in medium) t['id'] as String];
                final done = (context.watch<AppState>().answeredInMission[widget.nodeId] ?? {}).where(ids.contains).length;
                if (done > 0 && done < ids.length) return Text('Continue mission ($done of ${ids.length} done)');
                return Text(st['done'] == true ? 'Play again' : 'Start mission');
              }),
              onPressed: () => _startMission(title, [for (final i in items) i['id'] as String, for (final t in medium) t['id'] as String]),
            ),
            if (cards.isNotEmpty) ...[
              SizedBox(height: 24),
              Text('Learn objectives', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
              SizedBox(height: 8),
              for (final c in cards) ...[_LessonCard(card: c), SizedBox(height: 10)],
            ],
            SizedBox(height: 16),
            Text('Practise', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
            SizedBox(height: 8),
            if (items.isNotEmpty)
              _ActionTile(
                icon: Icons.quiz_outlined,
                title: '${items.length} questions',
                subtitle: '${st['items_answered']} of ${st['items_total']} scored questions answered',
                onTap: () => _run(TaskRun(title: title, taskIds: [for (final i in items) i['id'] as String])),
              ),
            for (final t in medium)
              _ActionTile(
                icon: Icons.show_chart,
                title: 'Day X: what happened next?',
                subtitle: _firstLine(t['brief'] as String),
                onTap: () => _run(TaskRun(title: 'Chart task', taskIds: [t['id'] as String])),
              ),
            SizedBox(height: 16),
            if (stepsTask != null)
              _ActionTile(
                icon: Icons.extension_rounded,
                title: 'Build your plan',
                subtitle: 'Snap the right steps together, in order.',
                onTap: _plan,
              ),
            SizedBox(height: 16),
            Text('Skip ahead', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
            SizedBox(height: 8),
            if ((st['prerequisite']['items'] as List).isNotEmpty)
              _ActionTile(
                icon: Icons.fact_check_outlined,
                title: st['prerequisite']['passed'] == true ? 'Prerequisite check passed' : 'Prerequisite check',
                subtitle: 'Questions from earlier skills. Get all right to finish the questions here.',
                onTap: () => _drawn('prerequisite-test', 'prerequisite', 'Prerequisite check'),
              ),
            _ActionTile(
              icon: Icons.bolt_outlined,
              title: st['test_out']['passed'] == true ? 'Test-out passed' : 'I know this already',
              subtitle: 'Two questions from this skill. Get both right to skip its questions.',
              onTap: () => _drawn('test-out', 'test_out', 'Test-out'),
            ),
          ]);
        },
      ),
    );
  }

  String _firstLine(String s) {
    final t = s.trim().split(RegExp(r'(?<=[.!?])\s')).first;
    return t.length > 110 ? '${t.substring(0, 107)}...' : t;
  }
}

class _StatusPanel extends StatelessWidget {
  final Map<String, dynamic> status;
  final bool hasMedium;
  _StatusPanel({required this.status, required this.hasMedium});

  @override
  Widget build(BuildContext context) {
    final done = status['done'] == true;
    Widget row(bool ok, String text) => Padding(
          padding: EdgeInsets.only(top: 6),
          child: Row(children: [
            Icon(ok ? Icons.check_circle : Icons.radio_button_unchecked, size: 18, color: ok ? kGreen : kFaint),
            SizedBox(width: 8),
            Expanded(child: Text(text, style: TextStyle(color: kBody))),
          ]),
        );
    final avg = status['item_average'];
    return Panel(
      color: done ? kGreenSoft : kSurface,
      border: done ? kGreen : kLine,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(done ? 'Skill complete' : 'To complete this skill',
            style: TextStyle(fontWeight: FontWeight.w800, color: done ? kGreen : kInk)),
        row(status['easy_done'] == true,
            'Questions: average 80% or more${avg == null ? '' : ' (now ${((avg as num) * 100).round()}%)'}, or pass a check'),
        if (hasMedium) row(status['medium_passed'] == true, 'Chart task: score 60% or more'),
      ]),
    );
  }
}

/// A learn objective: only the heading until tapped, then the full card.
class _LessonCard extends StatefulWidget {
  final Map<String, dynamic> card;
  _LessonCard({required this.card});
  @override
  State<_LessonCard> createState() => _LessonCardState();
}

class _LessonCardState extends State<_LessonCard> {
  bool open = false;

  @override
  Widget build(BuildContext context) {
    final card = widget.card;
    final links = (card['links'] as List? ?? []).cast<Map<String, dynamic>>();
    return Semantics(
      button: true,
      expanded: open,
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => setState(() => open = !open),
        child: Panel(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(child: Text(card['title'] as String, style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: kInk))),
              AnimatedRotation(
                turns: open ? 0.5 : 0,
                duration: Duration(milliseconds: 200),
                child: Icon(Icons.expand_more, color: kMuted),
              ),
            ]),
            AnimatedSize(
              duration: Duration(milliseconds: 220),
              curve: Curves.easeOutCubic,
              alignment: Alignment.topCenter,
              child: !open
                  ? SizedBox(width: double.infinity)
                  : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      SizedBox(height: 6),
                      Text(card['body'] as String, style: TextStyle(color: kBody, height: 1.4)),
                      if (card['example'] != null) ...[
                        SizedBox(height: 10),
                        Container(
                          width: double.infinity,
                          padding: EdgeInsets.all(10),
                          decoration: BoxDecoration(color: kPrimarySoft, borderRadius: BorderRadius.circular(10)),
                          child: Text('Example: ${card['example']}', style: TextStyle(color: kBody, fontSize: 13, height: 1.35)),
                        ),
                      ],
                      for (final l in links) ...[
                        SizedBox(height: 6),
                        Text('Source: ${l['title']}${l['publisher'] == null ? '' : ' (${l['publisher']})'}',
                            style: TextStyle(fontSize: 11, color: kMuted)),
                      ],
                    ]),
            ),
          ]),
        ),
      ),
    );
  }
}

class _ActionTile extends StatelessWidget {
  final IconData icon;
  final String title, subtitle;
  final VoidCallback onTap;
  _ActionTile({required this.icon, required this.title, required this.subtitle, required this.onTap});

  @override
  Widget build(BuildContext context) => Padding(
        padding: EdgeInsets.only(bottom: 10),
        child: Material(
          color: kSurface,
          borderRadius: BorderRadius.circular(16),
          child: ListTile(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: BorderSide(color: kLine)),
            leading: Icon(icon, color: kPrimaryText),
            title: Text(title, style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
            subtitle: Text(subtitle, style: TextStyle(fontSize: 12, color: kMuted)),
            trailing: Icon(Icons.chevron_right, color: kFaint),
            onTap: onTap,
          ),
        ),
      );
}
