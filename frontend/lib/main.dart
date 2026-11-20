// CrocoCash draft. Run: flutter run -d chrome   (web build: flutter build web)

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import 'data/app_state.dart';
import 'screens/onboarding_screen.dart';
import 'screens/wheel_screen.dart';
import 'screens/tree_screen.dart';
import 'screens/mission_screen.dart';
import 'screens/time_machine_screen.dart';
import 'screens/result_screen.dart';
import 'screens/placement_screen.dart';
import 'screens/progress_screen.dart';
import 'screens/shell.dart';
import 'screens/tutor_screen.dart';
import 'screens/league_screen.dart';
import 'screens/signin_screen.dart';
import 'screens/skills_screen.dart';
import 'screens/skill_screen.dart';
import 'screens/task_screen.dart';
import 'widgets/common.dart' show appDark;

void main() {
  runApp(ChangeNotifierProvider(create: (_) => AppState()..load(), child: FinanceQuestApp()));
}

final _router = GoRouter(
  initialLocation: '/',
  routes: [
    GoRoute(path: '/', builder: (_, __) => OnboardingScreen()),
    GoRoute(path: '/signin', builder: (_, __) => SignInScreen()),
    GoRoute(path: '/placement', builder: (_, st) => PlacementScreen(retest: st.uri.queryParameters['retest'] == '1')),
    ShellRoute(
      builder: (context, state, child) => AppShell(location: state.uri.path, child: child),
      routes: [
        GoRoute(path: '/wheel', builder: (_, __) => WheelScreen()),
        GoRoute(path: '/skills', builder: (_, __) => SkillsScreen()),
        GoRoute(path: '/tutor', builder: (_, __) => TutorScreen()),
        GoRoute(path: '/progress', builder: (_, __) => ProgressScreen()),
        GoRoute(path: '/league', builder: (_, __) => LeagueScreen()),
      ],
    ),
    GoRoute(path: '/slice/:key', builder: (_, s) => TreeScreen(sliceKey: s.pathParameters['key']!)),
    GoRoute(
      path: '/mission/:key/:node',
      builder: (_, s) => MissionScreen(sliceKey: s.pathParameters['key']!, nodeId: s.pathParameters['node']!),
    ),
    GoRoute(path: '/skill/:id', builder: (_, s) => SkillScreen(nodeId: s.pathParameters['id']!)),
    GoRoute(path: '/skill-run', builder: (_, s) => TaskRunScreen(run: s.extra as TaskRun)),
    GoRoute(path: '/time-machine', builder: (_, __) => TimeMachineScreen()),
    GoRoute(path: '/result', builder: (_, __) => ResultScreen()),
  ],
);

class FinanceQuestApp extends StatelessWidget {
  FinanceQuestApp({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    // Decide dark or light from the user's choice (or the system), before building,
    // so every screen uses the same palette with no in-between state.
    final systemDark = WidgetsBinding.instance.platformDispatcher.platformBrightness == Brightness.dark;
    appDark = switch (state.themeMode) { 'light' => false, 'dark' => true, _ => systemDark };
    const primary = Color(0xFF0E8430); // CrocoCash green, from the Figma frames
    ThemeData build(Brightness b) {
      final dark = b == Brightness.dark;
      final base = ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: primary,
          primary: dark ? const Color(0xFF8CDE6E) : primary,
          brightness: b,
          surface: dark ? const Color(0xFF1D1D1D) : Colors.white,
        ),
        scaffoldBackgroundColor: dark ? const Color(0xFF1D1D1D) : Colors.white,
        useMaterial3: true,
      );
      return base.copyWith(
        textTheme: GoogleFonts.interTextTheme(base.textTheme),
        appBarTheme: AppBarTheme(backgroundColor: base.scaffoldBackgroundColor, surfaceTintColor: Colors.transparent),
        navigationBarTheme: NavigationBarThemeData(
          backgroundColor: dark ? const Color(0xFF47673C) : const Color(0xFFB8EEA5),
          indicatorColor: dark ? const Color(0xFF1D1D1D) : Colors.white,
          surfaceTintColor: Colors.transparent,
        ),
        // Smooth transitions between pages on every platform.
        pageTransitionsTheme: const PageTransitionsTheme(builders: {
          TargetPlatform.android: FadeForwardsPageTransitionsBuilder(),
          TargetPlatform.iOS: FadeForwardsPageTransitionsBuilder(),
          TargetPlatform.macOS: FadeForwardsPageTransitionsBuilder(),
          TargetPlatform.windows: FadeForwardsPageTransitionsBuilder(),
          TargetPlatform.linux: FadeForwardsPageTransitionsBuilder(),
          TargetPlatform.fuchsia: FadeForwardsPageTransitionsBuilder(),
        }),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            backgroundColor: primary,
            foregroundColor: Colors.white,
            minimumSize: const Size.fromHeight(52),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          ),
        ),
      );
    }
    return MaterialApp.router(
      title: 'CrocoCash',
      debugShowCheckedModeBanner: false,
      theme: build(Brightness.light),
      darkTheme: build(Brightness.dark),
      themeMode: appDark ? ThemeMode.dark : ThemeMode.light,
      themeAnimationDuration: Duration.zero,
      routerConfig: _router,
      // Inclusive mode: respect system text size and allow an extra boost.
      builder: (context, child) {
        // Follow live system changes when the user picked "System".
        if (state.themeMode == 'system') {
          final d = MediaQuery.platformBrightnessOf(context) == Brightness.dark;
          if (d != appDark) WidgetsBinding.instance.addPostFrameCallback((_) => state.notify());
        }
        final mq = MediaQuery.of(context);
        final scale = mq.textScaler.scale(1) * (state.largeText ? 1.3 : 1.0);
        return MediaQuery(
          data: mq.copyWith(textScaler: TextScaler.linear(scale.clamp(1.0, 2.0))),
          child: Center(
            // Phone-width column on desktop browsers, full width on phones.
            child: ConstrainedBox(constraints: BoxConstraints(maxWidth: 480), child: child),
          ),
        );
      },
    );
  }
}
