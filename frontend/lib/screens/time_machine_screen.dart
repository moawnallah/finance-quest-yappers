// Time machine: split play money, replay 12 years, and see what staying calm does.
// It scores patience and diversification, never profit (lesson from Basis' The Floor).
// NOTE: the yearly growth factors below are an ILLUSTRATIVE SAMPLE for the draft.
// The real app loads WIG20TR / MSCI World (in PLN) and GUS CPI from the backend
// via POST /timemachine/run.

import 'dart:async';
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../widgets/common.dart';

const _years = [2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019];
// Sample growth factors per year (index fund, one company, cash after inflation).
const _index = [1.00, 0.60, 0.78, 0.92, 0.88, 1.00, 1.18, 1.25, 1.24, 1.33, 1.55, 1.48, 1.78];
const _single = [1.00, 0.45, 0.55, 0.62, 0.50, 0.48, 0.52, 0.40, 0.42, 0.47, 0.55, 0.50, 0.58];
const _cash = [1.00, 0.99, 0.98, 0.97, 0.96, 0.95, 0.94, 0.94, 0.94, 0.93, 0.92, 0.91, 0.90];

class TimeMachineScreen extends StatefulWidget {
  TimeMachineScreen({super.key});
  @override
  State<TimeMachineScreen> createState() => _TimeMachineScreenState();
}

class _TimeMachineScreenState extends State<TimeMachineScreen> {
  double single = 20, index = 60; // cash = rest
  int shown = 0;
  bool running = false;
  int? soldAt;
  Timer? timer;

  double get cash => (100 - single - index).clamp(0, 100);

  double valueAt(int i) {
    final stop = soldAt;
    final j = stop != null && i > stop ? stop : i; // selling freezes the value (and misses the recovery)
    final v = 10000 * (single / 100 * _single[j] + index / 100 * _index[j] + cash / 100 * _cash[j]);
    if (stop != null && i > stop) return v * _cash[i] / _cash[stop];
    return v;
  }

  void run() {
    timer?.cancel();
    setState(() { shown = 0; running = true; soldAt = null; });
    timer = Timer.periodic(Duration(milliseconds: 700), (t) {
      if (shown >= _years.length - 1) { t.cancel(); setState(() => running = false); return; }
      setState(() => shown++);
    });
  }

  @override
  void dispose() { timer?.cancel(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final finished = !running && shown == _years.length - 1;
    final stayedCalm = soldAt == null;
    final s = context.watch<AppState>();
    if (finished && stayedCalm && !s.badges.contains('calm')) {
      WidgetsBinding.instance.addPostFrameCallback((_) => s.earnBadge('calm'));
    }
    return Scaffold(
      appBar: StatsBar(title: 'Time machine', subtitle: 'Play money'),
      body: ListView(padding: EdgeInsets.all(20), children: [
        if (!s.coachSeen) ...[
          Panel(
            color: kPrimarySoft,
            border: kPrimarySoft,
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              MascotPlaceholder(size: 72, pose: 'think'),
              SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text("Let's do the first run together.", style: TextStyle(fontWeight: FontWeight.w700)),
                  SizedBox(height: 4),
                  Text('1. Split the money with the sliders. 2. Press Run. 3. When markets fall, decide: sell or hold. Then you try it alone.'),
                  TextButton(onPressed: s.markCoachSeen, child: Text('Got it')),
                ]),
              ),
            ]),
          ),
          SizedBox(height: 12),
        ],
        Text('Invest 10,000 zł of play money', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
        SizedBox(height: 12),
        _slider('One company', single, (v) => setState(() { single = v; if (single + index > 100) index = 100 - single; })),
        _slider('Global index fund', index, (v) => setState(() { index = v; if (single + index > 100) single = 100 - index; })),
        Text('Cash: ${cash.round()}%', style: TextStyle(color: kMuted)),
        SizedBox(height: 12),
        Panel(
          child: SizedBox(
            height: 200,
            child: LineChart(LineChartData(
              minY: 0,
              gridData: FlGridData(show: false),
              borderData: FlBorderData(show: false),
              titlesData: FlTitlesData(
                leftTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
                rightTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
                topTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
                bottomTitles: AxisTitles(sideTitles: SideTitles(
                  showTitles: true, interval: 4,
                  getTitlesWidget: (v, _) => Text('${_years[v.toInt()]}', style: TextStyle(fontSize: 10)),
                )),
              ),
              lineBarsData: [
                LineChartBarData(
                  spots: [for (var i = 0; i <= shown; i++) FlSpot(i.toDouble(), valueAt(i))],
                  color: kPrimary, barWidth: 3, dotData: FlDotData(show: false),
                ),
              ],
            )),
          ),
        ),
        SizedBox(height: 8),
        Text('${_years[shown]}: ${valueAt(shown).round()} zł', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
        Text('Sample curve for the draft. The app will replay real WIG20TR and MSCI World history.',
            style: TextStyle(fontSize: 11, color: kMuted)),
        SizedBox(height: 12),
        if (running && shown >= 1 && soldAt == null)
          OutlinedButton.icon(
            onPressed: () => setState(() => soldAt = shown),
            icon: Icon(Icons.trending_down),
            label: Text('Markets are falling. Sell everything?'),
          ),
        if (!running && !finished) FilledButton(onPressed: run, child: Text('Run 12 years')),
        if (finished) ...[
          TutorBubble(
            text: stayedCalm
                ? 'You stayed in through the crash. Your mix fell too, but holding a diversified mix gave it time to recover. That patience is the skill this mission trains.'
                : 'You sold in ${_years[soldAt!]}, which turned a temporary fall into a permanent loss and missed the recovery. Many people feel this urge; recognising it is the first step.',
          ),
          SizedBox(height: 12),
          if (stayedCalm)
            Panel(color: kWarnSoft, border: Color(0xFFFDB022), child: Text('Badge earned: Stayed calm in a crash')),
          SizedBox(height: 12),
          FilledButton(onPressed: () => context.go('/wheel'), child: Text('Back to the wheel')),
          TextButton(onPressed: run, child: Text('Replay')),
        ],
      ]),
    );
  }

  Widget _slider(String label, double value, ValueChanged<double> onChanged) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [Text(label), Spacer(), Text('${value.round()}%', style: TextStyle(fontWeight: FontWeight.w700))]),
          Slider(value: value, min: 0, max: 100, divisions: 20, onChanged: running ? null : onChanged),
        ],
      );
}
