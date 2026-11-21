// Bottom navigation shell (pattern used by Finanz and Basis).

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../data/sfx.dart';
import '../widgets/common.dart' show isWideWeb, PageWidth, TutorFab;

class AppShell extends StatelessWidget {
  final Widget child;
  final String location;
  AppShell({super.key, required this.child, required this.location});

  static const tabs = [
    ('/wheel', Icons.donut_large_outlined, Icons.donut_large, 'Explore'),
    ('/path', Icons.map_outlined, Icons.map, 'Path'),
    ('/league', Icons.leaderboard_outlined, Icons.leaderboard, 'League'),
    ('/progress', Icons.emoji_events_outlined, Icons.emoji_events, 'Progress'),
  ];

  @override
  Widget build(BuildContext context) {
    var index = tabs.indexWhere((t) => location.startsWith(t.$1));
    if (index < 0) index = 0;
    if (isWideWeb(context)) {
      // Desktop browser: the tabs sit in the top bar (StatsBar), the page fills the window.
      // On Explore the big Kyle opens the tutor; the round button is on the other tabs.
      return Scaffold(body: child, floatingActionButton: location.startsWith('/wheel') ? null : TutorFab());
    }
    return Scaffold(
      body: child,
      floatingActionButton: TutorFab(),
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (i) {
          if (i != index) Sfx.tap();
          context.go(tabs[i].$1);
        },
        destinations: [
          for (final t in tabs) NavigationDestination(icon: Icon(t.$2), selectedIcon: Icon(t.$3), label: t.$4),
        ],
      ),
    );
  }
}
