// Progress: today's goal, level, the three badges, the quick-check retest,
// and how Scales are earned. The league has its own tab.

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show SystemMouseCursors;
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
      body: PageWidth(max: 1000, child: ListView(padding: EdgeInsets.fromLTRB(20, 16, 20, 20), children: [
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
                  BadgeMedal(id: b.id, earned: s.badges.contains(b.id)),
                  SizedBox(height: 4),
                  Text(b.title, textAlign: TextAlign.center, style: TextStyle(fontSize: 12, color: s.badges.contains(b.id) ? kInk : kMuted)),
                ]),
              ),
            ),
        ]),
        SizedBox(height: 16),
        _Calibration(points: s.calibration),
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
      ])),
    );
  }
}

/// Confidence vs correctness: how sure the user said they were (1-5) against
/// the score they actually got, one dot per finished mission. The dashed line
/// is perfect self-assessment (sure 1 = 20%, sure 5 = 100%).
class _Calibration extends StatelessWidget {
  final List<(String, double, double, String?)> points;
  _Calibration({required this.points});

  @override
  Widget build(BuildContext context) {
    String verdict = 'Finish a mission and answer "How sure are you?" to see how well your confidence matches your results.';
    if (points.isNotEmpty) {
      final gap = points.map((p) => p.$2 * 20 - p.$3 * 100).reduce((a, b) => a + b) / points.length;
      verdict = gap > 15
          ? 'You tend to feel surer than your results. Slow down on questions you feel certain about.'
          : gap < -15
              ? 'You know more than you think. Trust yourself a little more.'
              : 'Your confidence matches your results well.';
    }
    return Panel(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('How well do you know what you know?', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
        SizedBox(height: 4),
        Text(verdict, style: TextStyle(color: kBody, height: 1.35)),
        SizedBox(height: 12),
        SizedBox(
          height: 200,
          child: LineChart(
            LineChartData(
              minX: 1, maxX: 5, minY: 0, maxY: 100,
              gridData: FlGridData(show: true, horizontalInterval: 25, verticalInterval: 1, getDrawingHorizontalLine: (_) => FlLine(color: kLine, strokeWidth: 1), getDrawingVerticalLine: (_) => FlLine(color: kLine, strokeWidth: 1)),
              borderData: FlBorderData(show: false),
              // Tap a dot to reopen the mission it came from.
              lineTouchData: LineTouchData(
                enabled: true,
                handleBuiltInTouches: false,
                touchSpotThreshold: 18,
                touchCallback: (event, resp) {
                  if (event is! FlTapUpEvent) return;
                  final hit = resp?.lineBarSpots?.where((b) => b.barIndex == 1).firstOrNull;
                  if (hit == null) return;
                  final skill = points[hit.spotIndex].$4;
                  if (skill != null) GoRouter.of(context).push('/skill/$skill');
                },
                mouseCursorResolver: (event, resp) =>
                    (resp?.lineBarSpots?.any((b) => b.barIndex == 1) ?? false) ? SystemMouseCursors.click : SystemMouseCursors.basic,
              ),
              titlesData: FlTitlesData(
                topTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
                rightTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
                bottomTitles: AxisTitles(
                  axisNameWidget: Text('How sure you were', style: TextStyle(fontSize: 11, color: kMuted)),
                  sideTitles: SideTitles(showTitles: true, interval: 1, reservedSize: 22, getTitlesWidget: (v, m) => Text('${v.toInt()}', style: TextStyle(fontSize: 11, color: kMuted))),
                ),
                leftTitles: AxisTitles(
                  axisNameWidget: Text('Score', style: TextStyle(fontSize: 11, color: kMuted)),
                  sideTitles: SideTitles(showTitles: true, interval: 25, reservedSize: 34, getTitlesWidget: (v, m) => Text('${v.toInt()}%', style: TextStyle(fontSize: 10, color: kMuted))),
                ),
              ),
              lineBarsData: [
                // Perfect self-assessment.
                LineChartBarData(spots: [FlSpot(1, 20), FlSpot(5, 100)], color: kFaint, barWidth: 1.5, dashArray: [6, 4], dotData: FlDotData(show: false)),
                // One dot per mission.
                LineChartBarData(
                  spots: [for (final p in points) FlSpot(p.$2.clamp(1, 5).toDouble(), (p.$3 * 100).clamp(0, 100).toDouble())],
                  color: Colors.transparent,
                  barWidth: 0,
                  dotData: FlDotData(show: true, getDotPainter: (s, _, __, ___) => FlDotCirclePainter(radius: 6, color: kPrimary, strokeWidth: 2, strokeColor: Colors.white)),
                ),
              ],
            ),
          ),
        ),
        SizedBox(height: 6),
        Row(children: [
          Container(width: 10, height: 10, decoration: BoxDecoration(color: kPrimary, shape: BoxShape.circle)),
          SizedBox(width: 6),
          Text('A mission (tap to open it)', style: TextStyle(fontSize: 11, color: kMuted)),
          SizedBox(width: 14),
          Container(width: 16, height: 2, color: kFaint),
          SizedBox(width: 6),
          Text('Confidence matches the score', style: TextStyle(fontSize: 11, color: kMuted)),
        ]),
      ]),
    );
  }
}
