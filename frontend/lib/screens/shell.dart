// Bottom navigation shell (pattern used by Finanz and Basis).

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class AppShell extends StatelessWidget {
  final Widget child;
  final String location;
  AppShell({super.key, required this.child, required this.location});

  static const tabs = [
    ('/wheel', Icons.donut_large_outlined, Icons.donut_large, 'Explore'),
    ('/practice', Icons.show_chart_outlined, Icons.show_chart, 'Practice'),
    ('/tutor', Icons.auto_awesome_outlined, Icons.auto_awesome, 'Tutor'),
    ('/progress', Icons.emoji_events_outlined, Icons.emoji_events, 'Progress'),
    ('/profile', Icons.person_outline, Icons.person, 'Profile'),
  ];

  @override
  Widget build(BuildContext context) {
    var index = tabs.indexWhere((t) => location.startsWith(t.$1));
    if (index < 0) index = 0;
    return Scaffold(
      body: child,
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
