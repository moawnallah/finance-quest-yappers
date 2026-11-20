// Sign-in (demo), required to start: Google or an email link. Nothing here
// creates a real account; the backend's auth replaces it.
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
      context.pop(true);
    } else {
      context.go('/wheel');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Save your progress')),
      body: ListView(padding: EdgeInsets.all(20), children: [
        Center(child: MascotPlaceholder(size: 84)),
        SizedBox(height: 16),
        Text('Sign in to keep your Scales, streak and roadmap on every device.',
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
          onPressed: () async {
            if (await googleSignInDemo(context, signIn: false)) _finish('Google user');
          },
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
        SizedBox(height: 8),
        Text('Demo screen: no account is created and nothing is stored.',
            textAlign: TextAlign.center, style: TextStyle(fontSize: 11, color: kMuted)),
      ]),
    );
  }
}

/// Demo of Google sign-in: explains what the real flow does, then signs in.
/// Returns true when the user continued.
Future<bool> googleSignInDemo(BuildContext context, {bool signIn = true}) async {
  final ok = await showDialog<bool>(
    context: context,
    builder: (d) => AlertDialog(
      title: Text('Google sign-in (demo)'),
      content: Text("In the real app this opens Google's own sign-in window. We would only get your name and email, to save your progress."),
      actions: [
        TextButton(onPressed: () => Navigator.pop(d, false), child: Text('Cancel')),
        FilledButton(onPressed: () => Navigator.pop(d, true), child: Text('Continue')),
      ],
    ),
  );
  if (ok == true && signIn && context.mounted) context.read<AppState>().signIn('Google user');
  return ok == true;
}
