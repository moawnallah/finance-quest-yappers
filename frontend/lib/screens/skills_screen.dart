// Skills tab: the skills-tree nodes served by the backend's task engines (GET /skills),
// grouped by panel, with this learner's progress on each node.

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../widgets/common.dart';

const panelNames = {
  'FOUNDATIONS': 'Foundations',
  'SAFETY': 'Safety net',
  'INSTRUMENTS': 'Instruments',
  'PORTFOLIO': 'Portfolio',
  'DECISIONS': 'Decisions',
  'LIFE': 'Life stages',
  'OWNERSHIP': 'Ownership',
};

String panelName(String p) => panelNames[p] ?? (p.isEmpty ? p : p[0] + p.substring(1).toLowerCase());

class SkillsScreen extends StatefulWidget {
  SkillsScreen({super.key});
  @override
  State<SkillsScreen> createState() => _SkillsScreenState();
}

class _SkillsScreenState extends State<SkillsScreen> {
  late Future<List<Map<String, dynamic>>> future;

  @override
  void initState() {
    super.initState();
    future = _load();
  }

  Future<List<Map<String, dynamic>>> _load() {
    final s = context.read<AppState>();
    return s.api.skills(s.profile.name);
  }

  void _reload() => setState(() => future = _load());

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: StatsBar(title: 'Skills'),
      body: FutureBuilder<List<Map<String, dynamic>>>(
        future: future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) return Center(child: CircularProgressIndicator());
          if (snap.hasError) return ErrorPanel(message: '${snap.error}', onRetry: _reload);
          final skills = snap.data!;
          if (skills.isEmpty) return Center(child: Text('No skills yet.', style: TextStyle(color: kMuted)));
          final panels = <String, List<Map<String, dynamic>>>{};
          for (final sk in skills) {
            panels.putIfAbsent(sk['panel'] as String, () => []).add(sk);
          }
          final done = skills.where((sk) => sk['status']['done'] == true).length;
          return RefreshIndicator(
            onRefresh: () async => _reload(),
            child: ListView(padding: EdgeInsets.fromLTRB(16, 8, 16, 24), children: [
              Text('$done of ${skills.length} skills complete', style: TextStyle(color: kMuted, fontWeight: FontWeight.w600)),
              SizedBox(height: 8),
              LinearProgressIndicator(value: skills.isEmpty ? 0 : done / skills.length, minHeight: 8, color: kPrimary, borderRadius: BorderRadius.circular(4)),
              for (final e in panels.entries) ...[
                SizedBox(height: 20),
                Text(panelName(e.key).toUpperCase(),
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, letterSpacing: .6, color: kPrimaryText)),
                SizedBox(height: 8),
                for (final sk in e.value) ...[
                  _SkillTile(skill: sk, onTap: () async {
                    await context.push('/skill/${sk['id']}');
                    _reload();
                  }),
                  SizedBox(height: 10),
                ],
              ],
            ]),
          );
        },
      ),
    );
  }
}

class _SkillTile extends StatelessWidget {
  final Map<String, dynamic> skill;
  final VoidCallback onTap;
  _SkillTile({required this.skill, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final st = skill['status'] as Map<String, dynamic>;
    final done = st['done'] == true;
    final answered = (st['items_correct'] as int?) ?? 0, total = st['items_total'] as int;
    final medium = skill['medium_tasks'] as int;
    final parts = [
      '${skill['cards']} cards',
      '$answered/$total questions right',
      if (medium > 0) st['medium_passed'] == true ? 'chart task passed' : '$medium chart task${medium == 1 ? '' : 's'}',
    ];
    return Material(
      color: done ? kGreenSoft : kSurface,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Container(
          padding: EdgeInsets.all(14),
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(16), border: Border.all(color: done ? kGreen : kLine)),
          child: Row(children: [
            CircleAvatar(
              radius: 20,
              backgroundColor: done ? kPrimary : kPrimarySoft,
              child: done
                  ? Icon(Icons.check, color: Colors.white)
                  : Text(skill['id'] as String, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: kPrimaryText)),
            ),
            SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(skill['title'] as String, style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: kInk)),
                SizedBox(height: 2),
                Text(parts.join(' · '), style: TextStyle(fontSize: 12, color: kMuted)),
                if (st['easy_done'] == true && !done) ...[
                  SizedBox(height: 2),
                  Text('Questions done. Pass the chart task to finish.', style: TextStyle(fontSize: 12, color: kPrimaryText)),
                ],
              ]),
            ),
            Icon(Icons.chevron_right, color: kFaint),
          ]),
        ),
      ),
    );
  }
}

/// Shown when a backend call fails, with a retry button.
class ErrorPanel extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  ErrorPanel({super.key, required this.message, required this.onRetry});

  // A missing mission or task cannot be fixed by retrying: offer the way back instead.
  bool get _missing => RegExp(r'^No (skill node|task)|not.found', caseSensitive: false).hasMatch(message);

  @override
  Widget build(BuildContext context) => Padding(
        padding: EdgeInsets.all(20),
        child: Center(
          child: Panel(
            color: kWarnSoft,
            border: kWarnBorder,
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Icon(_missing ? Icons.search_off : Icons.cloud_off, color: kWarnIcon, size: 32),
              SizedBox(height: 8),
              Text(message, textAlign: TextAlign.center, style: TextStyle(color: kWarnText)),
              SizedBox(height: 12),
              _missing
                  ? FilledButton.icon(onPressed: () => context.go('/wheel'), icon: Icon(Icons.arrow_back), label: Text('Back to the map'))
                  : FilledButton(onPressed: onRetry, child: Text('Try again')),
            ]),
          ),
        ),
      );
}
