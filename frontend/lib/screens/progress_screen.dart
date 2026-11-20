// Progress: today's goal, level, the three badges, the quick-check retest,
// and how Scales are earned. The league has its own tab.

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../widgets/common.dart';

class ProgressScreen extends StatelessWidget {
  ProgressScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final lvl = s.level, next = s.nextLevel;
    final today = s.xpToday, goal = s.dailyGoal;
    final reached = today >= goal;
    return Scaffold(
      appBar: StatsBar(title: 'Your progress'),
      body: ListView(padding: EdgeInsets.fromLTRB(20, 0, 20, 20), children: [
        // Today's goal, in words and a bar.
        Panel(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Text('Today', style: TextStyle(fontWeight: FontWeight.w700, color: kMuted)),
              Spacer(),
              if (reached) Icon(Icons.check_circle, color: kGreen, size: 20),
            ]),
            SizedBox(height: 6),
            Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
              ScaleIcon(size: 26),
              SizedBox(width: 8),
              Text('$today', style: TextStyle(fontSize: 30, fontWeight: FontWeight.w800, color: kInk, height: 1)),
              Padding(
                padding: EdgeInsets.only(bottom: 3, left: 6),
                child: Text('of $goal Scales', style: TextStyle(color: kMuted)),
              ),
            ]),
            SizedBox(height: 10),
            ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: LinearProgressIndicator(value: (today / goal).clamp(0, 1).toDouble(), minHeight: 10, color: kGreen, backgroundColor: kLine),
            ),
            SizedBox(height: 6),
            Text(reached ? 'Daily goal reached. Nice work.' : '${goal - today} more Scales to reach today\'s goal.',
                style: TextStyle(color: kBody)),
          ]),
        ),
        SizedBox(height: 12),
        // Level.
        Panel(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              for (final (i, l) in levels.indexed) ...[
                if (i > 0) Expanded(child: Divider(color: s.xp >= l.minXp ? kGreen : kLine, thickness: 3)),
                Column(children: [
                  CircleAvatar(
                    radius: 14,
                    backgroundColor: s.xp >= l.minXp ? kPrimary : kLine,
                    child: Icon(l == lvl ? Icons.star_rounded : s.xp >= l.minXp ? Icons.check : Icons.lock, size: 15, color: s.xp >= l.minXp ? Colors.white : kFaint),
                  ),
                  SizedBox(height: 4),
                  Text(l.name, style: TextStyle(fontSize: 11, fontWeight: l == lvl ? FontWeight.w800 : FontWeight.w500, color: l == lvl ? kInk : kMuted)),
                ]),
              ],
            ]),
            SizedBox(height: 10),
            Text(next == null ? 'You reached the top level.' : '${next.minXp - s.xp} Scales to ${next.name}.', style: TextStyle(color: kBody)),
          ]),
        ),
        SizedBox(height: 12),
        // Badges: three, shown small.
        Text('Badges', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
        SizedBox(height: 8),
        Row(children: [
          for (final b in badgeDefs)
            Expanded(
              child: Tooltip(
                message: b.rule,
                child: Column(children: [
                  CircleAvatar(
                    radius: 22,
                    backgroundColor: s.badges.contains(b.id) ? Color(0xFFFDB022) : kLine,
                    child: Icon(Icons.emoji_events, color: s.badges.contains(b.id) ? Color(0xFF7A2E0E) : kFaint),
                  ),
                  SizedBox(height: 4),
                  Text(b.title, textAlign: TextAlign.center, style: TextStyle(fontSize: 12, color: s.badges.contains(b.id) ? kInk : kMuted)),
                ]),
              ),
            ),
        ]),
        SizedBox(height: 16),
        Panel(
          child: Row(children: [
            Icon(Icons.quiz_outlined, color: kPrimaryText),
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
        Text('How you earn Scales', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
        SizedBox(height: 6),
        for (final (what, n) in [
          ('Correct answer', Rewards.correctAnswer),
          ('Mission finished', Rewards.missionDone),
          ("Today's question", Rewards.dailyRight),
          ('Quick check finished', Rewards.quickCheck),
        ])
          Padding(
            padding: EdgeInsets.symmetric(vertical: 4),
            child: Row(children: [
              Expanded(child: Text(what, style: TextStyle(color: kBody))),
              Text('+$n', style: TextStyle(fontWeight: FontWeight.w700, color: kPrimaryText)),
              SizedBox(width: 4),
              ScaleIcon(size: 14),
            ]),
          ),
      ]),
    );
  }
}
