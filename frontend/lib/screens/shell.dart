// Bottom navigation shell (pattern used by Finanz and Basis).

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class AppShell extends StatelessWidget {
  final Widget child;
  final String location;
  AppShell({super.key, required this.child, required this.location});

  static const tabs = [
    ('/wheel', Icons.donut_large_outlined, Icons.donut_large, 'Explore'),
    ('/skills', Icons.school_outlined, Icons.school, 'Skills'),
    ('/league', Icons.leaderboard_outlined, Icons.leaderboard, 'League'),
    ('/tutor', Icons.auto_awesome_outlined, Icons.auto_awesome, 'Tutor'),
    ('/progress', Icons.emoji_events_outlined, Icons.emoji_events, 'Progress'),
  ];

  @override
  Widget build(BuildContext context) {
    var index = tabs.indexWhere((t) => location.startsWith(t.$1));
    if (index < 0) index = 0;
    return Scaffold(
      body: AnimatedSwitcher(
        duration: Duration(milliseconds: 250),
        switchInCurve: Curves.easeOut,
        child: KeyedSubtree(key: ValueKey(tabs[index].$1), child: child),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (i) => context.go(tabs[i].$1),
        destinations: [
          for (final t in tabs) NavigationDestination(icon: Icon(t.$2), selectedIcon: Icon(t.$3), label: t.$4),
        ],
      ),
    );
  }
}
