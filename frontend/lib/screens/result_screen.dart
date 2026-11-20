// Mission result: XP, confidence after, first real step, and the bank hand-off.
// The hand-off is a mock here; in a bank embed it becomes a deep link into the
// bank's own product (for example eMakler: open an IKE account).

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../widgets/common.dart';

class ResultScreen extends StatefulWidget {
  ResultScreen({super.key});
  @override
  State<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends State<ResultScreen> {
  final checks = [false, false, false];

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final p = s.profile;
    return Scaffold(
      appBar: StatsBar(title: 'Mission complete', subtitle: 'Nice work'),
      body: ListView(padding: EdgeInsets.all(20), children: [
        CircleAvatar(radius: 40, backgroundColor: Color(0xFFFDB022), child: Icon(Icons.emoji_events, size: 40, color: Color(0xFF7A2E0E))),
        SizedBox(height: 16),
        Panel(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('How ready do you feel to invest now?', style: TextStyle(fontWeight: FontWeight.w600)),
            SizedBox(height: 10),
            Wrap(spacing: 8, children: [
              for (var i = 1; i <= 5; i++)
                ChoiceChip(label: Text('$i'), selected: p.confidenceAfter == i, onSelected: (_) => setState(() => p.confidenceAfter = i)),
            ]),
            if (p.confidenceAfter != null) ...[
              SizedBox(height: 8),
              Text('Before: ${p.confidenceBefore}  ·  Now: ${p.confidenceAfter}', style: TextStyle(color: kGreen, fontWeight: FontWeight.w600)),
            ],
          ]),
        ),
        SizedBox(height: 12),
        Panel(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('YOUR FIRST REAL STEP', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: kPrimaryText)),
            for (final (i, t) in ['Pick a monthly amount you won\'t miss, e.g. 100 zł', 'Compare two global index funds by their yearly fee', 'Learn how an IKE account works']
                .indexed)
              CheckboxListTile(value: checks[i], onChanged: (v) => setState(() => checks[i] = v ?? false), title: Text(t), contentPadding: EdgeInsets.zero),
          ]),
        ),
        if (!s.signedIn) ...[
          SizedBox(height: 12),
          // Learn first, sign up later (Duolingo pattern): ask only after a finished mission.
          Panel(
            color: kPrimarySoft,
            border: kTutorBorder,
            child: Row(children: [
              Icon(Icons.cloud_upload_outlined, color: kPrimary),
              SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('Save your progress', style: TextStyle(fontWeight: FontWeight.w700, color: kPrimaryText)),
                  Text('Keep your ${s.xp} XP and streak, on any device.', style: TextStyle(color: kBody)),
                ]),
              ),
              TextButton(onPressed: () => context.push('/signin'), child: Text('Save')),
            ]),
          ),
        ],
        SizedBox(height: 12),
        OutlinedButton(onPressed: () => context.push('/time-machine'), child: Text('Try the time machine')),
        TextButton(onPressed: () => context.go('/wheel'), child: Text('Back to the wheel')),
        SizedBox(height: 8),
        Text('Educational simulation, not financial advice.', textAlign: TextAlign.center, style: TextStyle(fontSize: 12, color: kMuted)),
      ]),
    );
  }
}
