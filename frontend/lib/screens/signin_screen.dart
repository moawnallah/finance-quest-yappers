// Sign-in (demo). Guest-first: signing in only saves progress, with Google or an email link.
// Nothing here creates a real account or stores data.

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../widgets/common.dart';

class SignInScreen extends StatefulWidget {
  SignInScreen({super.key});
  @override
  State<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends State<SignInScreen> {
  final email = TextEditingController();
  bool sent = false;

  void _finish(String name) {
    context.read<AppState>().signIn(name);
    if (context.canPop()) {
      context.pop();
    } else {
      context.go('/wheel');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Save your progress')),
      body: ListView(padding: EdgeInsets.all(20), children: [
        Center(
          child: Container(
            width: 72, height: 72,
            decoration: BoxDecoration(color: kPrimarySoft, shape: BoxShape.circle),
            child: Icon(Icons.lock_outline, size: 34, color: kPrimary),
          ),
        ),
        SizedBox(height: 16),
        Text('Sign in to keep your XP, streak and roadmap on every device.',
            textAlign: TextAlign.center, style: TextStyle(fontSize: 16, color: kBody, height: 1.4)),
        SizedBox(height: 24),
        // Google sign-in (demo). The real version uses Google OAuth (Firebase Auth
        // or google_sign_in), which needs a Google Cloud OAuth client first.
        OutlinedButton(
          style: OutlinedButton.styleFrom(
            minimumSize: Size.fromHeight(52),
            backgroundColor: kSurface,
            side: BorderSide(color: kBorder),
          ),
          onPressed: () => showDialog(
            context: context,
            builder: (d) => AlertDialog(
              title: Text('Google sign-in (demo)'),
              content: Text('In the real app this opens Google\'s own sign-in window. We would only get your name and email, to save your progress.'),
              actions: [
                TextButton(onPressed: () => Navigator.pop(d), child: Text('Cancel')),
                FilledButton(onPressed: () { Navigator.pop(d); _finish('Google user'); }, child: Text('Continue')),
              ],
            ),
          ),
          child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            Text('G', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: Color(0xFF4285F4))),
            SizedBox(width: 10),
            Text('Continue with Google (demo)', style: TextStyle(color: kInk, fontWeight: FontWeight.w600)),
          ]),
        ),
        SizedBox(height: 20),
        Row(children: [
          Expanded(child: Divider(color: kLine)),
          Padding(padding: EdgeInsets.symmetric(horizontal: 10), child: Text('or', style: TextStyle(color: kMuted))),
          Expanded(child: Divider(color: kLine)),
        ]),
        SizedBox(height: 20),
        Text('Email', style: TextStyle(fontWeight: FontWeight.w700)),
        SizedBox(height: 8),
        TextField(
          controller: email,
          keyboardType: TextInputType.emailAddress,
          decoration: InputDecoration(
            hintText: 'you@example.com',
            filled: true,
            fillColor: kSurface,
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
          ),
        ),
        SizedBox(height: 6),
        Text('No password. We send a one-time sign-in link.', style: TextStyle(fontSize: 12, color: kMuted)),
        SizedBox(height: 12),
        FilledButton(
          onPressed: () => setState(() => sent = true),
          child: Text('Send me a sign-in link (demo)'),
        ),
        if (sent) ...[
          SizedBox(height: 12),
          Panel(
            color: kGreenSoft,
            border: kGreen,
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Demo: no email is sent.', style: TextStyle(fontWeight: FontWeight.w700, color: kGreen)),
              SizedBox(height: 4),
              Text('In the real app you would tap the link in your inbox.', style: TextStyle(color: kBody)),
              SizedBox(height: 8),
              FilledButton(
                onPressed: () {
                  final e = email.text.trim();
                  _finish(e.contains('@') ? e.split('@').first : 'Learner');
                },
                child: Text('Simulate opening the link'),
              ),
            ]),
          ),
        ],
        SizedBox(height: 16),
        TextButton(onPressed: () => context.canPop() ? context.pop() : context.go('/'), child: Text('Not now, stay a guest')),
        SizedBox(height: 8),
        Text('Demo screen: no account is created and nothing is stored.',
            textAlign: TextAlign.center, style: TextStyle(fontSize: 11, color: kMuted)),
      ]),
    );
  }
}
