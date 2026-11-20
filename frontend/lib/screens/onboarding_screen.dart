import 'dart:math' as math;
// Onboarding: a step-by-step flow with a progress bar (idea borrowed from Finanz),
// with sign-in (Google or email link) first, then a few questions. No surname,
// phone, review prompt or countdown offers.

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import 'signin_screen.dart' show googleSignInDemo;
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
            Expanded(child: step == 0 ? pages[0] : SingleChildScrollView(child: pages[step])),
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

/// Landing page: one screen, no scrolling. Logo, a single message, three
/// short value points and one sign-in action.
class _Welcome extends StatelessWidget {
  final VoidCallback onStart;
  _Welcome({required this.onStart});

  Widget _point(IconData icon, String text) => Padding(
        padding: EdgeInsets.symmetric(vertical: 7),
        child: Row(children: [
          Icon(icon, size: 20, color: kPrimaryText),
          SizedBox(width: 12),
          Expanded(child: Text(text, style: TextStyle(fontSize: 15, color: kBody))),
        ]),
      );

  @override
  Widget build(BuildContext context) => LayoutBuilder(builder: (context, c) {
        final compact = c.maxHeight < 640;
        return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          SizedBox(height: compact ? 4 : 12),
          // Logo: crocodile eyes over the wordmark.
          Row(children: [
            Container(
              width: 40, height: 40,
              decoration: BoxDecoration(color: kPrimary, borderRadius: BorderRadius.circular(11)),
              alignment: Alignment.bottomCenter,
              child: Padding(padding: EdgeInsets.only(bottom: 9), child: CrocoEyes(width: 28)),
            ),
            SizedBox(width: 10),
            Text('CrocoCash', style: GoogleFonts.lora(fontSize: 22, fontWeight: FontWeight.w700, color: kInk)),
          ]),
          Spacer(flex: 3),
          Text('Invest with\nconfidence.',
              style: GoogleFonts.lora(fontSize: compact ? 36 : 44, fontWeight: FontWeight.w700, color: kInk, height: 1.08)),
          SizedBox(height: 14),
          Text('Short, practical lessons on 13 investment types, for every stage of life.',
              style: TextStyle(fontSize: 17, color: kMuted, height: 1.45)),
          SizedBox(height: compact ? 20 : 32),
          Align(alignment: Alignment.centerLeft, child: Container(width: 40, height: 3, decoration: BoxDecoration(color: kPrimary, borderRadius: BorderRadius.circular(2)))),
          SizedBox(height: compact ? 12 : 20),
          _point(Icons.schedule, 'Five minutes a day'),
          _point(Icons.account_tree_outlined, 'A clear path, from calm to wild'),
          _point(Icons.verified_outlined, 'Education only, never sales'),
          SizedBox(height: 12),
          // A quiet preview of the home wheel, peeking up from the bottom.
          Expanded(flex: 4, child: ExcludeSemantics(child: CustomPaint(painter: _WheelPeekPainter(), size: Size.infinite))),
          SizedBox(height: 12),
          OutlinedButton(
            style: OutlinedButton.styleFrom(
              minimumSize: Size.fromHeight(54),
              backgroundColor: kSurface,
              side: BorderSide(color: kBorder),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
            ),
            onPressed: () async {
              if (await googleSignInDemo(context)) onStart();
            },
            child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              GoogleG(size: 20),
              SizedBox(width: 12),
              Text('Continue with Google', style: TextStyle(fontSize: 16, color: kInk, fontWeight: FontWeight.w600)),
            ]),
          ),
          SizedBox(height: 14),
          Text('Educational content, not financial advice.', textAlign: TextAlign.center, style: TextStyle(fontSize: 12, color: kMuted)),
          SizedBox(height: 4),
        ]);
      });
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

/// Decorative half wheel for the landing page: the same green slices, rim and
/// crocodile hub as the home screen, without labels.
class _WheelPeekPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    if (size.height < 60) return;
    canvas.clipRect(Offset.zero & size); // stay inside the space above the button
    final r = math.min(size.width * 0.5, size.height * 0.95);
    final c = Offset(size.width / 2, size.height + r * 0.05);
    const n = 13;
    final step = 2 * math.pi / n, rim = r * 0.12, hub = r * 0.38, face = r - rim;
    for (var i = 0; i < n; i++) {
      final a0 = -math.pi / 2 + i * step - step / 2;
      final path = Path()
        ..arcTo(Rect.fromCircle(center: c, radius: face), a0, step, true)
        ..arcTo(Rect.fromCircle(center: c, radius: hub), a0 + step, -step, false)
        ..close();
      canvas.drawPath(path, Paint()..color = i == 0 ? kWheelFaceSel : kWheelFace);
      final dir = Offset(math.cos(a0), math.sin(a0));
      canvas.drawLine(c + dir * hub, c + dir * face, Paint()..color = kWheelLine..strokeWidth = 2);
    }
    canvas.drawCircle(c, r - rim / 2, Paint()..color = kWheelRim..style = PaintingStyle.stroke..strokeWidth = rim);
    canvas.drawCircle(c, hub, Paint()..color = kHub);
    canvas.drawCircle(c, hub - 3, Paint()..color = kHubRim..style = PaintingStyle.stroke..strokeWidth = 5);
    paintCrocoEyes(canvas, Offset(c.dx, c.dy - hub + hub * 0.12), hub * 0.95, kHub);
    // Pointer at the top.
    final top = Offset(c.dx, c.dy - r - 3);
    canvas.drawPath(
        Path()
          ..moveTo(top.dx - 9, top.dy - 10)
          ..lineTo(top.dx + 9, top.dy - 10)
          ..lineTo(top.dx, top.dy + 3)
          ..close(),
        Paint()..color = kPrimary);
    // Soft fade into the page at the bottom edge.
    final fade = Rect.fromLTWH(0, size.height * 0.7, size.width, size.height * 0.3);
    canvas.drawRect(fade, Paint()..shader = LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [kBg.withValues(alpha: 0), kBg]).createShader(fade));
  }

  @override
  bool shouldRepaint(covariant CustomPainter old) => true;
}
