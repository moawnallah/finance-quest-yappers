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
                    s.startFromSurvey(); // the survey picks the starting topic
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

/// Landing page: compact sign-in. Email and password (demo: any password of
/// six or more characters), Google (demo), or continue as a guest. Signing in
/// with an admin email also unlocks the admin panel.
class _Welcome extends StatefulWidget {
  final VoidCallback onStart;
  _Welcome({required this.onStart});
  @override
  State<_Welcome> createState() => _WelcomeState();
}

class _WelcomeState extends State<_Welcome> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _hide = true;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  void _signIn() {
    final email = _email.text.trim();
    final ok = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch(email);
    if (!ok) return setState(() => _error = 'Enter a valid email address.');
    if (_password.text.length < 6) return setState(() => _error = 'The password needs at least 6 characters.');
    setState(() => _error = null);
    context.read<AppState>().signInWithEmail(email);
    widget.onStart();
  }

  InputDecoration _field(String label, IconData icon, {Widget? suffix}) => InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon, size: 20),
        suffixIcon: suffix,
        filled: true,
        fillColor: kSurface,
        isDense: true,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
      );

  @override
  Widget build(BuildContext context) => LayoutBuilder(builder: (context, c) {
        return SingleChildScrollView(
          child: ConstrainedBox(
            constraints: BoxConstraints(minHeight: c.maxHeight),
            child: IntrinsicHeight(
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                SizedBox(height: 8),
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
                Spacer(),
                Text('Invest with confidence.', style: GoogleFonts.lora(fontSize: 32, fontWeight: FontWeight.w700, color: kInk, height: 1.1)),
                SizedBox(height: 8),
                Text('Short, practical lessons on investment types, for every stage of life.',
                    style: TextStyle(fontSize: 16, color: kMuted, height: 1.4)),
                SizedBox(height: 24),
                TextField(
                  controller: _email,
                  keyboardType: TextInputType.emailAddress,
                  autofillHints: [AutofillHints.email],
                  textInputAction: TextInputAction.next,
                  decoration: _field('Email', Icons.mail_outline),
                ),
                SizedBox(height: 10),
                TextField(
                  controller: _password,
                  obscureText: _hide,
                  autofillHints: [AutofillHints.password],
                  onSubmitted: (_) => _signIn(),
                  decoration: _field('Password', Icons.lock_outline,
                      suffix: IconButton(
                        tooltip: _hide ? 'Show password' : 'Hide password',
                        icon: Icon(_hide ? Icons.visibility_outlined : Icons.visibility_off_outlined, size: 20),
                        onPressed: () => setState(() => _hide = !_hide),
                      )),
                ),
                if (_error != null) ...[
                  SizedBox(height: 8),
                  Text(_error!, style: TextStyle(color: kRed, fontSize: 13)),
                ],
                SizedBox(height: 12),
                FilledButton(onPressed: _signIn, child: Text('Sign in')),
                SizedBox(height: 14),
                Row(children: [
                  Expanded(child: Divider(color: kLine)),
                  Padding(padding: EdgeInsets.symmetric(horizontal: 10), child: Text('or', style: TextStyle(color: kMuted))),
                  Expanded(child: Divider(color: kLine)),
                ]),
                SizedBox(height: 14),
                OutlinedButton(
                  style: OutlinedButton.styleFrom(
                    minimumSize: Size.fromHeight(52),
                    backgroundColor: kSurface,
                    side: BorderSide(color: kBorder),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                  ),
                  onPressed: () async {
                    if (await googleSignInDemo(context)) widget.onStart();
                  },
                  child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                    GoogleG(size: 20),
                    SizedBox(width: 12),
                    Text('Continue with Google', style: TextStyle(fontSize: 16, color: kInk, fontWeight: FontWeight.w600)),
                  ]),
                ),
                SizedBox(height: 4),
                TextButton(
                  onPressed: () {
                    context.read<AppState>().signInAsGuest();
                    widget.onStart();
                  },
                  child: Text('Continue as guest'),
                ),
                SizedBox(height: 8),
                Row(children: [
                  Expanded(child: _StoreButton(icon: Icons.apple, small: 'Download on the', big: 'App Store')),
                  SizedBox(width: 10),
                  Expanded(child: _StoreButton(icon: Icons.play_arrow_rounded, small: 'Get it on', big: 'Google Play')),
                ]),
                Spacer(),
                Text('Educational content, not financial advice.', textAlign: TextAlign.center, style: TextStyle(fontSize: 12, color: kMuted)),
                SizedBox(height: 4),
              ]),
            ),
          ),
        );
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
        Slider(value: years.toDouble(), min: 1, max: 40, divisions: 39, onChanged: (v) => onChanged(v.round())),
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

/// Store download button. The apps are not listed yet, so it says so.
class _StoreButton extends StatelessWidget {
  final IconData icon;
  final String small, big;
  _StoreButton({required this.icon, required this.small, required this.big});
  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        label: '$small $big',
        excludeSemantics: true,
        child: Material(
          color: Colors.black,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
            side: BorderSide(color: appDark ? Colors.white38 : Colors.black), // visible on the dark background too
          ),
          child: InkWell(
            borderRadius: BorderRadius.circular(10),
            onTap: () => ScaffoldMessenger.of(context)
              ..hideCurrentSnackBar()
              ..showSnackBar(SnackBar(content: Text('CrocoCash is coming to the $big soon.'))),
            child: Padding(
              padding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                Icon(icon, color: Colors.white, size: 26),
                SizedBox(width: 6),
                Flexible(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                    Text(small, style: TextStyle(color: Colors.white70, fontSize: 9.5, height: 1.1)),
                    Text(big, maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w700, height: 1.1)),
                  ]),
                ),
              ]),
            ),
          ),
        ),
      );
}
