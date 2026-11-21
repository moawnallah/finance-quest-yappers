// Path tab: the learning path recommended from the starting survey and quick
// check. Served by the backend router (GET /me/path, backend/ml/router); the
// app only shows it. Steps without content yet are marked "coming later".

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../widgets/common.dart';
import 'skills_screen.dart' show ErrorPanel;
import 'drawn_test.dart';
import 'package:url_launcher/url_launcher.dart';

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
            icon: Icon(Icons.map),
            label: Text('Start the survey'),
          ),
        ),
        SizedBox(height: 8),
        Center(child: Text('About 2 minutes. You can retake it any time.', style: TextStyle(color: kMuted))),
      ]);

  Future<void> _choose(AppState s, String id) async {
    try {
      await s.api.choosePath(s.profile.name, id);
    } catch (_) {}
    if (mounted) setState(() => _data = _load());
  }

  void _changePlan(BuildContext context, AppState s, Map<String, dynamic> d, List<Map<String, dynamic>> options) {
    showModalBottomSheet(
      context: context,
      useRootNavigator: true,
      constraints: BoxConstraints(maxWidth: 560),
      builder: (ctx) => SafeArea(
        child: ListView(shrinkWrap: true, padding: EdgeInsets.all(20), children: [
          Text('Change plan', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: kInk)),
          SizedBox(height: 4),
          Text('Your progress is kept when you switch: every answer counts on every path.', style: TextStyle(color: kMuted)),
          SizedBox(height: 12),
          ListTile(
            leading: Icon(Icons.auto_awesome, color: kPrimaryText),
            title: Text('Recommended', style: TextStyle(fontWeight: FontWeight.w700)),
            subtitle: Text('The path from your starting survey'),
            trailing: d['source'] != 'chosen' ? Icon(Icons.check, color: kGreen) : null,
            onTap: () {
              Navigator.pop(ctx);
              _choose(s, 'recommended');
            },
          ),
          for (final o in options)
            ListTile(
              leading: Icon(Icons.map_outlined, color: kPrimaryText),
              title: Text('${o['title']}', style: TextStyle(fontWeight: FontWeight.w700)),
              subtitle: o['for'] == null ? null : Text('${o['for']}'),
              trailing: d['path_id'] == o['id'] ? Icon(Icons.check, color: kGreen) : null,
              onTap: () {
                Navigator.pop(ctx);
                _choose(s, o['id'] as String);
              },
            ),
        ]),
      ),
    );
  }

  Future<void> _quickCheck(BuildContext context, Map<String, dynamic> c) async {
    final passed = await runDrawnTest(context, c['node'] as String, testOut: true, title: 'Quick check: ${c['title']}');
    if (!mounted || passed == null) return;
    setState(() => _data = _load());
    if (!context.mounted) return;
    if (passed) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Both right: "${c['title']}" is marked done.')));
    } else {
      await showDialog(
        context: context,
        builder: (d) => AlertDialog(
          title: Text('Not both right'),
          content: Text('The answers you just saw explain why. The full mission covers it step by step.'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(d), child: Text('Close')),
            FilledButton(
              style: FilledButton.styleFrom(minimumSize: Size(120, 44)),
              onPressed: () {
                Navigator.pop(d);
                context.push('/skill/${c['node']}');
              },
              child: Text('Open the mission'),
            ),
          ],
        ),
      );
    }
  }

  Future<void> _finish(BuildContext context, AppState s, Map<String, dynamic> d, List<Map<String, dynamic>> steps) async {
    final answers = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      useRootNavigator: true,
      constraints: BoxConstraints(maxWidth: 560),
      builder: (_) => _CheckIn(steps: steps),
    );
    if (answers == null || !context.mounted) return;
    Map<String, dynamic> r;
    try {
      r = await s.api.finishPath(s.profile.name, {'path_id': d['path_id'] ?? 'recommended', ...answers});
    } catch (e) {
      if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
      return;
    }
    if (!context.mounted) return;
    await showDialog(context: context, builder: (_) => _FinishReply(reply: r));
  }

  Widget _path(BuildContext context, AppState s, Map<String, dynamic> d) {
    final steps = (d['steps'] as List).cast<Map<String, dynamic>>();
    final challenges = (d['challenges'] as List? ?? []).cast<Map<String, dynamic>>();
    final demo = Map<String, dynamic>.from(d['demo'] as Map? ?? {});
    final options = (d['options'] as List? ?? []).cast<Map<String, dynamic>>();
    final done = steps.where((x) => x['done'] == true).length;
    final source = switch (d['source']) {
      'chosen' => 'The path you picked',
      _ => 'Recommended',
    };
    final allDone = steps.isNotEmpty && done == steps.length;
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
                if (d['goal'] != null) 'Goal topic: ${d['goal'] is Map ? (d['goal'] as Map)['title'] : '${d['goal']}'.replaceAll('_', ' ')}',
              ].join(' · '),
              style: TextStyle(color: kMuted),
            ),
            SizedBox(height: 10),
            ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: LinearProgressIndicator(value: steps.isEmpty ? 0 : done / steps.length, minHeight: 8, color: kGreen, backgroundColor: kLine),
            ),
            SizedBox(height: 8),
            Wrap(spacing: 8, runSpacing: 4, children: [
              if (options.isNotEmpty)
                TextButton.icon(onPressed: () => _changePlan(context, s, d, options), icon: Icon(Icons.swap_horiz), label: Text('Change plan')),
              if (d['source'] == 'chosen')
                TextButton.icon(onPressed: () => _choose(s, 'recommended'), icon: Icon(Icons.undo), label: Text('Back to my recommended path')),
            ]),
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
            Text(
              s.isAdmin
                  ? '${demo['message'] ?? 'The recommended path is not ready yet.'}\n(admin) recommended: ${(d['recommended'] as List? ?? []).join(' > ')} · demo status: ${demo['status']}'
                  : 'This path is not ready yet in the demo. Pick one of the ready paths:',
              style: TextStyle(color: kInk, height: 1.4),
            ),
            SizedBox(height: 10),
            Wrap(spacing: 8, runSpacing: 8, children: [
              for (final o in options)
                OutlinedButton(
                  onPressed: () => _choose(s, o['id'] as String),
                  child: Text('${o['title']}'),
                ),
            ]),
          ]),
        ),
      ],
      if (allDone) ...[
        SizedBox(height: 12),
        Panel(
          color: kGreenSoft,
          border: kGreen,
          child: Row(children: [
            Icon(Icons.flag_circle, color: kGreen, size: 32),
            SizedBox(width: 12),
            Expanded(child: Text('You finished every step of this path. Tell us how it went and see what to learn next.',
                style: TextStyle(color: kInk, height: 1.35))),
            SizedBox(width: 8),
            FilledButton(
              style: FilledButton.styleFrom(minimumSize: Size(110, 44)),
              onPressed: () => _finish(context, s, d, steps),
              child: Text('Finish'),
            ),
          ]),
        ),
      ],
      SizedBox(height: 16),
      Text('Steps', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: kInk)),
      SizedBox(height: 8),
      for (final (i, st) in steps.indexed) _Step(index: i, step: st, isNext: st['node'] == d['next'], last: i == steps.length - 1),
      if (challenges.any((c) => c['live'] == true)) ...[
        SizedBox(height: 16),
        Text('Quick checks', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: kInk)),
        Text('Topics you probably know already: answer 2 questions to skip them.', style: TextStyle(color: kMuted)),
        SizedBox(height: 8),
        for (final c in challenges.where((c) => c['live'] == true))
          Card(
            elevation: 0,
            color: kSurface,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14), side: BorderSide(color: kLine)),
            child: ListTile(
              leading: c['done'] == true ? Icon(Icons.check_circle, color: kGreen) : Icon(Icons.bolt, color: kWarnIcon),
              title: Text('${c['title']}', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
              subtitle: Text(c['done'] == true ? 'Done' : '${c['why'] ?? ''}', style: TextStyle(color: c['done'] == true ? kPrimaryText : kMuted)),
              trailing: c['done'] == true ? null : Icon(Icons.chevron_right),
              onTap: c['done'] == true ? null : () => _quickCheck(context, c),
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
                        Text('${step['correct'] ?? 0} of ${step['total']} questions right', style: TextStyle(fontSize: 12, color: kMuted)),
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


/// The end-of-path check-in: progress, confidence per step, next goal (POST /paths/finish).
class _CheckIn extends StatefulWidget {
  final List<Map<String, dynamic>> steps;
  _CheckIn({required this.steps});
  @override
  State<_CheckIn> createState() => _CheckInState();
}

class _CheckInState extends State<_CheckIn> {
  String? progress;
  String? goal;
  final Map<String, int> confidence = {};
  static const goals = {
    'buffer': 'An emergency buffer', 'first_investment': 'My first investment', 'retirement': 'Retirement',
    'home': 'A home', 'keep_learning': 'Keep learning', 'other': 'Something else',
  };

  @override
  Widget build(BuildContext context) {
    final ready = progress != null && goal != null;
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(20, 20, 20, 20 + MediaQuery.viewInsetsOf(context).bottom),
        child: SingleChildScrollView(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
            Text('How did it go?', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: kInk)),
            SizedBox(height: 12),
            Text('Did you make progress?', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
            SizedBox(height: 6),
            Wrap(spacing: 8, children: [
              for (final (v, l) in [('yes', 'Yes'), ('somewhat', 'Somewhat'), ('no', 'No')])
                ChoiceChip(label: Text(l), selected: progress == v, onSelected: (_) => setState(() => progress = v)),
            ]),
            SizedBox(height: 14),
            Text('How sure do you feel about each step? (1-5)', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
            for (final st in widget.steps.where((x) => x['live'] == true))
              Padding(
                padding: EdgeInsets.only(top: 8),
                child: Row(children: [
                  Expanded(child: Text('${st['title']}', style: TextStyle(color: kBody))),
                  for (final c in [1, 2, 3, 4, 5])
                    Padding(
                      padding: EdgeInsets.only(left: 4),
                      child: ChoiceChip(
                        label: Text('$c'),
                        visualDensity: VisualDensity.compact,
                        selected: confidence[st['node']] == c,
                        onSelected: (_) => setState(() => confidence[st['node'] as String] = c),
                      ),
                    ),
                ]),
              ),
            SizedBox(height: 14),
            Text('What is your next goal?', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
            SizedBox(height: 6),
            Wrap(spacing: 8, runSpacing: 6, children: [
              for (final e in goals.entries)
                ChoiceChip(label: Text(e.value), selected: goal == e.key, onSelected: (_) => setState(() => goal = e.key)),
            ]),
            SizedBox(height: 18),
            FilledButton(
              onPressed: ready ? () => Navigator.pop(context, {'progress': progress, 'confidence': confidence, 'next_goal': goal}) : null,
              child: Text('Send'),
            ),
          ]),
        ),
      ),
    );
  }
}

/// The reply: thanks, the other path, the next steps, and how people usually start with their own money.
class _FinishReply extends StatelessWidget {
  final Map<String, dynamic> reply;
  _FinishReply({required this.reply});

  @override
  Widget build(BuildContext context) {
    final next = (reply['next_steps'] as List? ?? []).cast<Map>();
    final other = reply['other_path'] as Map?;
    return AlertDialog(
      title: Text('Thank you!', textAlign: TextAlign.center),
      content: SizedBox(
        width: 520,
        child: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Center(child: MascotPlaceholder(size: 140, pose: 'cheer')),
            SizedBox(height: 8),
            Text('${reply['message'] ?? ''}', style: TextStyle(color: kBody, height: 1.4)),
            if (next.isNotEmpty) ...[
              SizedBox(height: 14),
              Text('What to learn next', style: TextStyle(fontWeight: FontWeight.w800, color: kInk)),
              for (final n in next)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(n['live'] == true ? Icons.play_circle_outline : Icons.hourglass_top_rounded,
                      color: n['live'] == true ? kPrimaryText : kWarnIcon),
                  title: Text('${n['title']}', style: TextStyle(fontWeight: FontWeight.w700)),
                  subtitle: n['reason'] == null ? null : Text('${n['reason']}'),
                  onTap: () {
                    Navigator.pop(context);
                    context.push(n['live'] == true ? '/skill/${n['node']}' : '/coming-later?node=${n['node']}');
                  },
                ),
            ],
            if (other != null) ...[
              SizedBox(height: 10),
              Text('Or try the other path: ${other['title']}', style: TextStyle(color: kMuted)),
            ],
            SizedBox(height: 14),
            Panel(
              color: kPrimarySoft,
              border: kPrimarySoft,
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Start with your own money', style: TextStyle(fontWeight: FontWeight.w800, color: kPrimaryText)),
                SizedBox(height: 6),
                Text('How people usually start: an emergency fund first, then a small monthly amount in shares '
                    'through a low-cost, diversified fund.', style: TextStyle(color: kInk, height: 1.4)),
                SizedBox(height: 6),
                Text('Before you buy: check the costs in the KID (key information document), and check the firm '
                    'in the KNF register.', style: TextStyle(color: kInk, height: 1.4)),
                SizedBox(height: 10),
                OutlinedButton.icon(
                  onPressed: () => openInvestmentAccountPage(),
                  icon: Icon(Icons.open_in_new),
                  label: Text("Open an investment account at the bank"),
                ),
                SizedBox(height: 4),
                Text('Educational information about types of investments, not advice about any product.',
                    style: TextStyle(fontSize: 11, color: kMuted)),
              ]),
            ),
          ]),
        ),
      ),
      actions: [FilledButton(style: FilledButton.styleFrom(minimumSize: Size(110, 44)), onPressed: () => Navigator.pop(context), child: Text('Close'))],
    );
  }
}


/// The bank's own page for opening an investment account (a service, not a recommended instrument).
/// Set with --dart-define=INVEST_ACCOUNT_URL; the wording and link are to be confirmed with the Commerzbank mentor.
const investAccountUrl = String.fromEnvironment('INVEST_ACCOUNT_URL', defaultValue: 'https://www.mbank.pl/indywidualny/inwestycje/');

Future<void> openInvestmentAccountPage() => launchUrl(Uri.parse(investAccountUrl), webOnlyWindowName: '_blank');
