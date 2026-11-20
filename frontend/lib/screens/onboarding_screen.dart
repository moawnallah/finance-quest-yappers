// Onboarding: a step-by-step flow with a progress bar (idea borrowed from Finanz),
// but guest-first: no email, surname, phone, review prompt or countdown offers.

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../widgets/common.dart';

class OnboardingScreen extends StatefulWidget {
  OnboardingScreen({super.key});
  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  int step = 0;
  static const total = 6;

  void next() => setState(() => step++);

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final p = s.profile;
    final pages = <Widget>[
      _Welcome(onStart: next),
      _Choice(
        title: 'How old are you?',
        options: ['18-29', '30-49', '50+'],
        selected: p.ageGroup,
        onPick: (v) => setState(() => p.ageGroup = v),
      ),
      _Choice(
        title: 'What are you investing for?',
        options: ['A first habit', 'Kids\' education', 'Retirement', 'A home', 'Not sure yet'],
        selected: p.goal,
        onPick: (v) => setState(() => p.goal = v),
      ),
      _Horizon(years: p.horizonYears, onChanged: (v) => setState(() => p.horizonYears = v)),
      _Choice(
        title: 'How much have you invested before?',
        options: ['None', 'A little', 'Quite a lot'],
        selected: p.experience,
        onPick: (v) => setState(() => p.experience = v),
      ),
      _Confidence(
        value: p.confidenceBefore,
        onPick: (v) => setState(() => p.confidenceBefore = v),
      ),
    ];

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: EdgeInsets.fromLTRB(20, 16, 20, 20),
          child: Column(children: [
            if (step > 0) ...[
              Row(children: [
                IconButton(onPressed: () => setState(() => step--), icon: Icon(Icons.arrow_back), tooltip: 'Back'),
                Expanded(
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(4),
                    child: LinearProgressIndicator(value: step / (total - 1), minHeight: 8, color: kPrimary, backgroundColor: kBorder),
                  ),
                ),
              ]),
              SizedBox(height: 16),
            ],
            Expanded(child: SingleChildScrollView(child: pages[step])),
            if (step > 0)
              FilledButton(
                onPressed: () {
                  if (step < total - 1) {
                    next();
                  } else {
                    s.notify();
                    context.go('/placement');
                  }
                },
                child: Text(step < total - 1 ? 'Continue' : 'Build my path'),
              ),
          ]),
        ),
      ),
    );
  }
}

class _Welcome extends StatelessWidget {
  final VoidCallback onStart;
  _Welcome({required this.onStart});

  Widget _feature(IconData icon, Color color, String title, String text) => Padding(
        padding: EdgeInsets.only(bottom: 10),
        child: Panel(
          child: Row(children: [
            Container(
              width: 44, height: 44,
              decoration: BoxDecoration(color: color.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(12)),
              child: Icon(icon, color: color),
            ),
            SizedBox(width: 14),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(title, style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                SizedBox(height: 2),
                Text(text, style: TextStyle(color: kMuted, height: 1.3)),
              ]),
            ),
          ]),
        ),
      );

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        SizedBox(height: 16),
        Row(children: [
          Container(
            width: 40, height: 40,
            decoration: BoxDecoration(color: kPrimary, borderRadius: BorderRadius.circular(12)),
            child: Icon(Icons.trending_up, color: Colors.white, size: 24),
          ),
          SizedBox(width: 10),
          Text('Finance Quest', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
        ]),
        SizedBox(height: 20),
        // Hero: the calm-to-bumpy colour scale used on the wheel.
        Container(
          padding: EdgeInsets.all(20),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF3B4FD8), Color(0xFF2A3AA8)]),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('From knowing to doing', style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800, color: Colors.white, height: 1.15)),
            SizedBox(height: 8),
            Text('Learn investing in 5 minutes a day, at any age. No account needed to start.',
                style: TextStyle(fontSize: 15, color: Color(0xFFDDE2FF), height: 1.4)),
            SizedBox(height: 16),
            Row(children: [
              for (var r = 1; r <= 5; r++)
                Expanded(
                  child: Container(
                    height: 10,
                    margin: EdgeInsets.only(right: r < 5 ? 4 : 0),
                    decoration: BoxDecoration(color: riskColor(r), borderRadius: BorderRadius.circular(5)),
                  ),
                ),
            ]),
            SizedBox(height: 6),
            Row(children: [
              Text('Calm', style: TextStyle(fontSize: 11, color: Color(0xFFDDE2FF))),
              Spacer(),
              Text('13 investment types', style: TextStyle(fontSize: 11, color: Color(0xFFDDE2FF))),
              Spacer(),
              Text('Bumpy', style: TextStyle(fontSize: 11, color: Color(0xFFDDE2FF))),
            ]),
          ]),
        ),
        SizedBox(height: 16),
        _feature(Icons.donut_large, kPrimary, '5-minute missions', 'A wheel of investment types, each with a short roadmap.'),
        _feature(Icons.history, Color(0xFF1F7A55), 'Time machine', 'Replay real market history with play money.'),
        _feature(Icons.auto_awesome, Color(0xFFB8551A), 'Tutor', 'Explains your mistakes using your own goal.'),
        SizedBox(height: 8),
        Wrap(alignment: WrapAlignment.center, spacing: 8, runSpacing: 8, children: [
          for (final t in ['Free', 'No ads', 'No trading', 'Larger text option'])
            Container(
              padding: EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), border: Border.all(color: kBorder)),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.check, size: 14, color: kGreen),
                SizedBox(width: 4),
                Text(t, style: TextStyle(fontSize: 12, color: kBody)),
              ]),
            ),
        ]),
        SizedBox(height: 24),
        FilledButton(onPressed: onStart, child: Text('Start as guest')),
        SizedBox(height: 10),
        OutlinedButton(
          onPressed: () => context.push('/signin'), // email sign-in (demo)
          style: OutlinedButton.styleFrom(minimumSize: Size.fromHeight(48)),
          child: Text('Sign in to continue my progress'),
        ),
        SizedBox(height: 14),
        Text('Educational content, not financial advice.', textAlign: TextAlign.center, style: TextStyle(fontSize: 12, color: kMuted)),
        SizedBox(height: 16),
      ]);
}

class _Choice extends StatelessWidget {
  final String title;
  final List<String> options;
  final String selected;
  final ValueChanged<String> onPick;
  _Choice({required this.title, required this.options, required this.selected, required this.onPick});

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title, style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800)),
        SizedBox(height: 20),
        for (final o in options)
          Padding(
            padding: EdgeInsets.only(bottom: 10),
            child: Semantics(
              selected: o == selected,
              button: true,
              child: InkWell(
                borderRadius: BorderRadius.circular(14),
                onTap: () => onPick(o),
                child: Container(
                  width: double.infinity,
                  constraints: BoxConstraints(minHeight: 56),
                  padding: EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                  decoration: BoxDecoration(
                    color: o == selected ? kPrimarySoft : kSurface,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: o == selected ? kPrimary : kBorder, width: o == selected ? 2 : 1),
                  ),
                  child: Text(o, style: TextStyle(fontSize: 16, fontWeight: o == selected ? FontWeight.w700 : FontWeight.w500)),
                ),
              ),
            ),
          ),
      ]);
}

class _Horizon extends StatelessWidget {
  final int years;
  final ValueChanged<int> onChanged;
  _Horizon({required this.years, required this.onChanged});
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('When will you need this money?', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800)),
        SizedBox(height: 32),
        Center(child: Text('$years years', style: TextStyle(fontSize: 44, fontWeight: FontWeight.w800, color: kPrimary))),
        Slider(value: years.toDouble(), min: 1, max: 40, divisions: 39, label: '$years', onChanged: (v) => onChanged(v.round())),
        Text('Your horizon shapes every mission and replay. Longer horizons can ride out bigger drops.',
            style: TextStyle(color: kMuted, height: 1.4)),
      ]);
}

class _Confidence extends StatelessWidget {
  final int value;
  final ValueChanged<int> onPick;
  _Confidence({required this.value, required this.onPick});
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('How ready do you feel to invest today?', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800)),
        SizedBox(height: 24),
        Row(children: [
          for (var i = 1; i <= 5; i++)
            Expanded(
              child: Padding(
                padding: EdgeInsets.symmetric(horizontal: 4),
                child: ChoiceChip(
                  label: SizedBox(height: 32, child: Center(child: Text('$i', style: TextStyle(fontSize: 18)))),
                  selected: value == i,
                  onSelected: (_) => onPick(i),
                  showCheckmark: false,
                ),
              ),
            ),
        ]),
        SizedBox(height: 8),
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Text('Not at all', style: TextStyle(color: kMuted)),
          Text('Fully ready', style: TextStyle(color: kMuted)),
        ]),
      ]);
}
