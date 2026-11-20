// Profile and settings: goal, horizon, daily goal and inclusive-mode switches.

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import 'package:go_router/go_router.dart';
import '../widgets/common.dart';

class ProfileScreen extends StatelessWidget {
  ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final p = s.profile;
    return Scaffold(
      appBar: StatsBar(title: 'Profile', subtitle: p.name),
      body: ListView(padding: EdgeInsets.all(20), children: [
        Panel(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Goal: ${p.goal}', style: TextStyle(fontWeight: FontWeight.w700)),
            SizedBox(height: 4),
            Text('Horizon: ${p.horizonYears} years · Age group: ${p.ageGroup} · Experience: ${p.experience}', style: TextStyle(color: kMuted)),
            if (p.placementScore != null) Text('Quick check: ${p.placementScore} of ${p.placementTotal}', style: TextStyle(color: kMuted)),
          ]),
        ),
        SizedBox(height: 16),
        Text('Appearance', style: TextStyle(fontWeight: FontWeight.w700)),
        SizedBox(height: 8),
        SegmentedButton<String>(
          showSelectedIcon: false,
          segments: [
            ButtonSegment(value: 'system', icon: Icon(Icons.brightness_auto), label: Text('System')),
            ButtonSegment(value: 'light', icon: Icon(Icons.light_mode), label: Text('Light')),
            ButtonSegment(value: 'dark', icon: Icon(Icons.dark_mode), label: Text('Dark')),
          ],
          selected: {s.themeMode},
          onSelectionChanged: (v) => s.setThemeMode(v.first),
        ),
        SizedBox(height: 16),
        Text('Accessibility', style: TextStyle(fontWeight: FontWeight.w700)),
        SwitchListTile(contentPadding: EdgeInsets.zero, title: Text('Larger text'), value: s.largeText, onChanged: s.setLargeText),
        SwitchListTile(contentPadding: EdgeInsets.zero, title: Text('List view instead of the wheel'), value: s.listView, onChanged: s.setListView),
        SizedBox(height: 8),
        Text('Daily goal', style: TextStyle(fontWeight: FontWeight.w700)),
        SizedBox(height: 8),
        SegmentedButton<int>(
          showSelectedIcon: false,
          segments: [ButtonSegment(value: 10, label: Text('10 XP')), ButtonSegment(value: 20, label: Text('20 XP')), ButtonSegment(value: 30, label: Text('30 XP'))],
          selected: {s.dailyGoal},
          onSelectionChanged: (v) => s.setDailyGoal(v.first),
        ),
        SizedBox(height: 24),
        Text('Account', style: TextStyle(fontWeight: FontWeight.w700)),
        if (!s.signedIn)
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(Icons.save_outlined),
            title: Text('Save my progress'),
            subtitle: Text('Sign in with Google or email'),
            trailing: Icon(Icons.chevron_right),
            onTap: () => context.push('/signin'),
          )
        else
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(Icons.verified_user_outlined, color: kGreen),
            title: Text('Signed in as ${p.name} (demo)'),
            trailing: TextButton(onPressed: s.signOut, child: Text('Sign out')),
          ),
        SizedBox(height: 8),
        Text('Educational content, not financial advice.', style: TextStyle(fontSize: 12, color: kMuted)),
      ]),
    );
  }
}
