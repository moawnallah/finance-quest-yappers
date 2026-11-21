// Path tab: the learning path recommended from the starting survey and quick
// check. Served by the backend router (GET /me/path, backend/ml/router); the
// app only shows it. Steps without content yet are marked "coming later".

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../widgets/common.dart';
import 'skills_screen.dart' show ErrorPanel;

class PathScreen extends StatefulWidget {
  PathScreen({super.key});
  @override
  State<PathScreen> createState() => _PathScreenState();
}

class _PathScreenState extends State<PathScreen> {
  Future<Map<String, dynamic>>? _data;
  DateTime? _loadedFor;

  Future<Map<String, dynamic>> _load() {
    final s = context.read<AppState>();
    return s.api.path(s.profile.name);
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    if (_data == null || _loadedFor != s.surveyAt) {
      _loadedFor = s.surveyAt;
      _data = _load();
    }
    return Scaffold(
      appBar: StatsBar(title: 'Your path', subtitle: 'From your starting survey'),
      body: PageWidth(
        max: 1000,
        child: FutureBuilder<Map<String, dynamic>>(
          future: _data,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) return Center(child: CircularProgressIndicator());
            if (snap.hasError) {
              return ListView(padding: EdgeInsets.all(20), children: [
                ErrorPanel(message: '${snap.error}', onRetry: () => setState(() => _data = _load())),
              ]);
            }
            final d = snap.data!;
            if (d['survey_done'] != true) return _noSurvey(context);
            return RefreshIndicator(
              onRefresh: () async => setState(() => _data = _load()),
              child: _path(context, s, d),
            );
          },
        ),
      ),
    );
  }

  Widget _noSurvey(BuildContext context) => ListView(padding: EdgeInsets.all(20), children: [
        SizedBox(height: 12),
        Center(child: KyleCallout(text: "Answer a few questions and a 5-question check, and I'll build a learning path just for you.", size: 220)),
        SizedBox(height: 20),
        Center(
          child: FilledButton.icon(
            style: FilledButton.styleFrom(minimumSize: Size(120, 44)),
            onPressed: () => context.go('/survey'),
            icon: Icon(Icons.route),
            label: Text('Start the survey'),
          ),
        ),
        SizedBox(height: 8),
        Center(child: Text('About 2 minutes. You can retake it any time.', style: TextStyle(color: kMuted))),
      ]);

  Widget _path(BuildContext context, AppState s, Map<String, dynamic> d) {
    final steps = (d['steps'] as List).cast<Map<String, dynamic>>();
    final challenges = (d['challenges'] as List? ?? []).cast<Map<String, dynamic>>();
    final demo = Map<String, dynamic>.from(d['demo'] as Map? ?? {});
    final options = (d['options'] as List? ?? []).cast<Map<String, dynamic>>();
    final done = steps.where((x) => x['done'] == true).length;
    final source = switch (d['source']) {
      'chosen' => 'The path you picked',
      'demo' => 'Recommended for you (a ready path)',
      'personal' => 'Recommended for you',
      _ => 'Recommended for you',
    };
    return ListView(padding: EdgeInsets.fromLTRB(20, 16, 20, 96), children: [
      Panel(
        child: Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(source.toUpperCase(), style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, letterSpacing: .6, color: kPrimaryText)),
            SizedBox(height: 4),
            Text('$done of ${steps.length} steps done', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: kInk)),
            SizedBox(height: 4),
            Text(
              [
                if (d['knowledge_score'] != null) 'Quick check: ${d['knowledge_score']} of 5',
                if (d['goal'] != null) 'Goal: ${'${d['goal']}'.replaceAll('_', ' ')}',
              ].join(' · '),
              style: TextStyle(color: kMuted),
            ),
            SizedBox(height: 10),
            ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: LinearProgressIndicator(value: steps.isEmpty ? 0 : done / steps.length, minHeight: 8, color: kGreen, backgroundColor: kLine),
            ),
          ])),
          SizedBox(width: 12),
          MascotPlaceholder(size: 150, pose: done == steps.length && steps.isNotEmpty ? 'cheer' : 'point', headOnPhone: true),
        ]),
      ),
      if (demo['status'] == 'not_ready' && options.isNotEmpty) ...[
        SizedBox(height: 12),
        Panel(
          color: kWarnSoft,
          border: kWarnBorder,
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${demo['message'] ?? 'Your recommended path is not ready yet.'}', style: TextStyle(color: kInk, height: 1.4)),
            SizedBox(height: 10),
            Wrap(spacing: 8, runSpacing: 8, children: [
              for (final o in options)
                OutlinedButton(
                  onPressed: () async {
                    await s.api.choosePath(s.profile.name, o['id'] as String);
                    setState(() => _data = _load());
                  },
                  child: Text('${o['title']}'),
                ),
            ]),
          ]),
        ),
      ],
      SizedBox(height: 16),
      Text('Steps', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: kInk)),
      SizedBox(height: 8),
      for (final (i, st) in steps.indexed) _Step(index: i, step: st, isNext: st['node'] == d['next'], last: i == steps.length - 1),
      if (challenges.isNotEmpty) ...[
        SizedBox(height: 16),
        Text('Quick checks', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: kInk)),
        Text('Topics you probably know already: answer 2 questions to skip them.', style: TextStyle(color: kMuted)),
        SizedBox(height: 8),
        for (final c in challenges)
          Card(
            elevation: 0,
            color: kSurface,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14), side: BorderSide(color: kLine)),
            child: ListTile(
              leading: Icon(Icons.bolt, color: kWarnIcon),
              title: Text('${c['title']}', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
              subtitle: Text('${c['why'] ?? ''}', style: TextStyle(color: kMuted)),
              trailing: Icon(Icons.chevron_right),
              onTap: () => context.push(c['live'] == true ? '/skill/${c['node']}' : '/coming-later?node=${c['node']}'),
            ),
          ),
      ],
      SizedBox(height: 16),
      Center(child: TextButton.icon(onPressed: () => context.go('/survey'), icon: Icon(Icons.replay), label: Text('Retake the starting survey'))),
    ]);
  }
}

class _Step extends StatelessWidget {
  final int index;
  final Map<String, dynamic> step;
  final bool isNext, last;
  _Step({required this.index, required this.step, required this.isNext, required this.last});

  @override
  Widget build(BuildContext context) {
    final live = step['live'] == true, done = step['done'] == true;
    final color = done ? kGreen : !live ? kWarnIcon : isNext ? kPrimary : kBorder;
    return IntrinsicHeight(
      child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        SizedBox(
          width: 44,
          child: Column(children: [
            Container(
              width: 34, height: 34,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: done ? kGreen : isNext ? kPrimary : kSurface,
                shape: BoxShape.circle,
                border: Border.all(color: color, width: 2),
              ),
              child: done
                  ? Icon(Icons.check, size: 18, color: Colors.white)
                  : Text('${index + 1}', style: TextStyle(fontWeight: FontWeight.w800, color: isNext ? Colors.white : kInk)),
            ),
            if (!last) Expanded(child: Container(width: 3, margin: EdgeInsets.symmetric(vertical: 4), color: done ? kGreen : kLine)),
          ]),
        ),
        SizedBox(width: 8),
        Expanded(
          child: Padding(
            padding: EdgeInsets.only(bottom: 12),
            child: Material(
              color: !live ? kWarnSoft : isNext ? kPrimarySoft : kSurface,
              borderRadius: BorderRadius.circular(14),
              child: InkWell(
                borderRadius: BorderRadius.circular(14),
                onTap: () => context.push(live ? '/skill/${step['node']}' : '/coming-later?node=${step['node']}'),
                child: Container(
                  padding: EdgeInsets.all(14),
                  decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), border: Border.all(color: !live ? kWarnBorder : isNext ? kPrimary : kLine)),
                  child: Row(children: [
                    Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Wrap(spacing: 6, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
                        Text('${step['title']}', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: kInk)),
                        if (isNext) _chip('Next', kPrimary),
                        if (!live) _chip('Coming later', kWarnIcon),
                        if (done) _chip('Done', kGreen),
                      ]),
                      if (step['reason'] != null) ...[
                        SizedBox(height: 4),
                        Text('${step['reason']}', style: TextStyle(color: kBody, height: 1.35)),
                      ],
                      if (live && (step['total'] ?? 0) > 0) ...[
                        SizedBox(height: 4),
                        Text('${step['answered']} of ${step['total']} questions answered', style: TextStyle(fontSize: 12, color: kMuted)),
                      ],
                    ])),
                    Icon(live ? Icons.chevron_right : Icons.schedule, color: kMuted),
                  ]),
                ),
              ),
            ),
          ),
        ),
      ]),
    );
  }

  Widget _chip(String t, Color c) => Container(
        padding: EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(color: c.withValues(alpha: .14), borderRadius: BorderRadius.circular(999), border: Border.all(color: c)),
        child: Text(t, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: c)),
      );
}

/// A topic that is planned but has no content yet.
class ComingLaterScreen extends StatelessWidget {
  final String nodeId;
  ComingLaterScreen({super.key, required this.nodeId});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    if (s.roadmapNodes.isEmpty) s.loadRoadmap();
    final n = s.roadmapNodes.where((x) => x['id'] == nodeId).firstOrNull;
    final title = (n?['title'] as String?) ?? nodeId;
    final panel = n == null ? '' : (panelLabels[n['panel']] ?? '${n['panel']}');
    final after = [for (final a in (n?['after'] as List? ?? [])) s.roadmapNodes.where((x) => x['id'] == a).firstOrNull?['title'] ?? a];
    return Scaffold(
      appBar: AppBar(title: Text('Coming later')),
      body: ListView(padding: EdgeInsets.all(24), children: [
        Center(child: MascotPlaceholder(size: 220, pose: 'think')),
        SizedBox(height: 12),
        if (panel.isNotEmpty)
          Center(child: Text(panel.toUpperCase(), style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, letterSpacing: .6, color: kWarnText))),
        SizedBox(height: 4),
        Center(child: Text(title, textAlign: TextAlign.center, style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800, color: kInk))),
        SizedBox(height: 12),
        Panel(
          color: kWarnSoft,
          border: kWarnBorder,
          child: Text("We're still writing this mission. It's on the map so you can see where it fits, and it will open in a later version.",
              style: TextStyle(color: kInk, height: 1.45)),
        ),
        if (after.isNotEmpty) ...[
          SizedBox(height: 12),
          Text('Builds on: ${after.join(', ')}', style: TextStyle(color: kMuted)),
        ],
        SizedBox(height: 20),
        Center(
          child: FilledButton.icon(
            style: FilledButton.styleFrom(minimumSize: Size(120, 44)),
            onPressed: () => context.canPop() ? context.pop() : context.go('/wheel'),
            icon: Icon(Icons.arrow_back),
            label: Text('Back'),
          ),
        ),
      ]),
    );
  }
}
