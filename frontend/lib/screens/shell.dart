// Bottom navigation shell (pattern used by Finanz and Basis).

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../data/sfx.dart';
import '../widgets/common.dart' show isWideWeb, PageWidth;

class AppShell extends StatelessWidget {
  final Widget child;
  final String location;
  AppShell({super.key, required this.child, required this.location});

  static const tabs = [
    ('/wheel', Icons.donut_large_outlined, Icons.donut_large, 'Explore'),
    ('/league', Icons.leaderboard_outlined, Icons.leaderboard, 'League'),
    ('/tutor', Icons.auto_awesome_outlined, Icons.auto_awesome, 'Tutor'),
    ('/progress', Icons.emoji_events_outlined, Icons.emoji_events, 'Progress'),
  ];

  @override
  Widget build(BuildContext context) {
    var index = tabs.indexWhere((t) => location.startsWith(t.$1));
    if (index < 0) index = 0;
    void select(int i) {
      if (i != index) Sfx.tap();
      context.go(tabs[i].$1);
    }

    final body = AnimatedSwitcher(
      duration: Duration(milliseconds: 250),
      switchInCurve: Curves.easeOut,
      // Explore and Tutor use the full width (wheel, conversation list); other tabs a readable column.
      child: KeyedSubtree(key: ValueKey(tabs[index].$1), child: index == 0 || tabs[index].$1 == '/tutor' ? child : PageWidth(child: child)),
    );
    if (isWideWeb(context)) {
      // Desktop browser: a navigation rail on the left, the page fills the rest.
      return Scaffold(
        body: Row(children: [
          NavigationRail(
            selectedIndex: index,
            onDestinationSelected: select,
            labelType: NavigationRailLabelType.all,
            backgroundColor: Theme.of(context).navigationBarTheme.backgroundColor,
            indicatorColor: Theme.of(context).navigationBarTheme.indicatorColor,
            destinations: [
              for (final t in tabs) NavigationRailDestination(icon: Icon(t.$2), selectedIcon: Icon(t.$3), label: Text(t.$4)),
            ],
          ),
          Expanded(child: body),
        ]),
      );
    }
    return Scaffold(
      body: AnimatedSwitcher(
        duration: Duration(milliseconds: 250),
        switchInCurve: Curves.easeOut,
        child: KeyedSubtree(key: ValueKey(tabs[index].$1), child: child),
      ),
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
