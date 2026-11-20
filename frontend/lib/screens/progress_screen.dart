// Progress: level ladder, daily goal ring, badges and a weekly league
// (ideas from Basis and Finanz). The league rows are labelled demo data.

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import 'package:go_router/go_router.dart';
import '../widgets/common.dart';

class ProgressScreen extends StatelessWidget {
  ProgressScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final next = s.nextLevel;
    final league = [
      ('Demo learner A', 180), ('Demo learner B', 140), ('You', s.xp), ('Demo learner C', 60), ('Demo learner D', 20),
    ]..sort((a, b) => b.$2.compareTo(a.$2));
    return Scaffold(
      appBar: StatsBar(title: 'Your progress', subtitle: s.level.name),
      body: ListView(padding: EdgeInsets.all(20), children: [
        Panel(
          child: Row(children: [
            SizedBox(
              width: 72, height: 72,
              child: Stack(alignment: Alignment.center, children: [
                CircularProgressIndicator(value: (s.xpToday / s.dailyGoal).clamp(0, 1), strokeWidth: 8, color: kGreen, backgroundColor: kLine),
                Text('${s.xpToday}/${s.dailyGoal}', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12)),
              ]),
            ),
            SizedBox(width: 16),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Level: ${s.level.name}', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 18)),
                Text(next == null ? 'Top level reached' : '${next.minXp - s.xp} XP to ${next.name}', style: TextStyle(color: kMuted)),
                SizedBox(height: 4),
                Text('Streak: ${s.streak} day${s.streak == 1 ? '' : 's'}', style: TextStyle(color: kMuted)),
              ]),
            ),
          ]),
        ),
        SizedBox(height: 12),
        Panel(
          child: Row(children: [
            Icon(Icons.quiz_outlined, color: kPrimary),
            SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Check your progress', style: TextStyle(fontWeight: FontWeight.w700)),
                Text(
                  s.profile.placementScore == null
                      ? 'Take the 5-question quick check'
                      : 'First check: ${s.profile.placementScore} of 5${s.profile.retestScore != null ? ' · latest: ${s.profile.retestScore} of 5' : ''}',
                  style: TextStyle(color: kMuted),
                ),
              ]),
            ),
            TextButton(
              onPressed: () => context.push(s.profile.placementScore == null ? '/placement' : '/placement?retest=1'),
              child: Text(s.profile.placementScore == null ? 'Start' : 'Retake'),
            ),
          ]),
        ),
        SizedBox(height: 16),
        Text('Levels', style: TextStyle(fontWeight: FontWeight.w700)),
        SizedBox(height: 8),
        Wrap(spacing: 8, runSpacing: 8, children: [
          for (final l in levels)
            Chip(
              label: Text('${l.name} · ${l.minXp}'),
              backgroundColor: s.xp >= l.minXp ? kPrimarySoft : kSurface,
              side: BorderSide(color: s.level == l ? kPrimary : kBorder),
            ),
        ]),
        SizedBox(height: 16),
        Text('Badges', style: TextStyle(fontWeight: FontWeight.w700)),
        SizedBox(height: 8),
        for (final b in badgeDefs)
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: CircleAvatar(
              backgroundColor: s.badges.contains(b.id) ? Color(0xFFFDB022) : kLine,
              child: Icon(Icons.emoji_events, color: s.badges.contains(b.id) ? Color(0xFF7A2E0E) : kFaint),
            ),
            title: Text(b.title, style: TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Text(b.rule),
          ),
        SizedBox(height: 16),
        Text('Weekly league (demo data)', style: TextStyle(fontWeight: FontWeight.w700)),
        SizedBox(height: 4),
        Text('Ranks learning XP only.', style: TextStyle(fontSize: 12, color: kMuted)),
        SizedBox(height: 8),
        for (final (i, row) in league.indexed)
          Panel(
            color: row.$1 == 'You' ? kPrimarySoft : null,
            child: Row(children: [
              SizedBox(width: 28, child: Text('${i + 1}', style: TextStyle(fontWeight: FontWeight.w700))),
              Expanded(child: Text(row.$1)),
              Text('${row.$2} XP', style: TextStyle(fontWeight: FontWeight.w600)),
            ]),
          ),
      ]),
    );
  }
}
