import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:finance_quest/data/api.dart';
import 'package:finance_quest/data/app_state.dart';
import 'package:finance_quest/screens/task_screen.dart';
import 'package:finance_quest/widgets/common.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('ExplanationBubble renders explanation without crocodile mascot or tutor prompt', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: ExplanationBubble(text: '6,500 - 5,100 = 1,400 PLN.'),
      ),
    ));

    expect(find.text('Explanation'), findsOneWidget);
    expect(find.text('Educational, not advice'), findsNothing);
    expect(find.text('6,500 - 5,100 = 1,400 PLN.'), findsOneWidget);
    expect(find.byType(MascotPlaceholder), findsNothing);
    expect(find.text('Ask the tutor about this'), findsNothing);
  });

  testWidgets('AskTutorBubble renders crocodile mascot and tutor prompt, and calls onAsk', (tester) async {
    var asked = false;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: AskTutorBubble(onAsk: () => asked = true),
      ),
    ));

    expect(find.byType(MascotPlaceholder), findsOneWidget);
    expect(find.text('Ask the tutor about this'), findsOneWidget);
    expect(find.byIcon(Icons.chevron_right), findsOneWidget);

    await tester.tap(find.text('Ask the tutor about this'));
    await tester.pumpAndSettle();
    expect(asked, isTrue);
  });

  testWidgets('TutorBubble separates explanation and ask tutor prompt into two distinct boxes', (tester) async {
    var asked = false;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: TutorBubble(
          text: 'This is the written explanation.',
          onAsk: () => asked = true,
        ),
      ),
    ));

    expect(find.byType(ExplanationBubble), findsOneWidget);
    expect(find.byType(AskTutorBubble), findsOneWidget);
    expect(find.text('This is the written explanation.'), findsOneWidget);
    expect(find.text('Ask the tutor about this'), findsOneWidget);

    // Mascot is only inside AskTutorBubble, not ExplanationBubble
    final mascotInAskTutor = find.descendant(
      of: find.byType(AskTutorBubble),
      matching: find.byType(MascotPlaceholder),
    );
    expect(mascotInAskTutor, findsOneWidget);

    final mascotInExplanation = find.descendant(
      of: find.byType(ExplanationBubble),
      matching: find.byType(MascotPlaceholder),
    );
    expect(mascotInExplanation, findsNothing);
  });

  testWidgets('TaskRunScreen displays separated explanation and ask tutor box next to the answer', (tester) async {
    final fx = jsonDecode(File('test/fixtures/api.json').readAsStringSync()) as Map<String, dynamic>;
    final client = MockClient((req) async {
      final key = '${req.method} ${req.url.path}';
      if (!fx.containsKey(key)) return http.Response('{"error":{"code":"not_found","message":"$key"}}', 404);
      return http.Response(jsonEncode(fx[key]), 200, headers: {'content-type': 'application/json'});
    });

    SharedPreferences.setMockInitialValues({});
    tester.view.physicalSize = Size(600, 1200);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);

    final state = AppState()..api = Api(client: client, baseUrl: 'http://test');
    var navigatedToTutorChat = false;
    final router = GoRouter(routes: [
      GoRoute(path: '/', builder: (_, __) => TaskRunScreen(run: TaskRun(title: 'Numeric test', taskIds: ['i2.e2']))),
      GoRoute(path: '/tutor-chat', builder: (_, __) {
        navigatedToTutorChat = true;
        return Scaffold(body: Text('Tutor Chat Screen'));
      }),
    ]);

    final repaintKey = GlobalKey();
    await tester.pumpWidget(
      ChangeNotifierProvider.value(
        value: state,
        child: MaterialApp.router(
          routerConfig: router,
          builder: (context, child) => RepaintBoundary(key: repaintKey, child: child),
        ),
      ),
    );
    await tester.pumpAndSettle();

    // Check slider and answer submission
    final slider = find.byType(Slider);
    expect(slider, findsOneWidget);
    await tester.tap(slider);
    await tester.pumpAndSettle();

    final sure = find.byKey(ValueKey('confidence-4'));
    if (sure.evaluate().isNotEmpty) {
      await tester.tap(sure);
      await tester.pumpAndSettle();
    }

    await tester.tap(find.text('Check my answer'));
    await tester.pumpAndSettle();

    // Verify layout after reveal:
    // 1. Answer text is present
    expect(find.textContaining('Answer:'), findsOneWidget);

    // 2. ExplanationBubble is present next to the answer
    expect(find.byType(ExplanationBubble), findsOneWidget);
    expect(find.text('Explanation'), findsOneWidget);
    expect(find.text('Educational, not advice'), findsNothing);

    // 3. AskTutorBubble is present as a separate box
    expect(find.byType(AskTutorBubble), findsOneWidget);
    expect(find.text('Ask the tutor about this'), findsOneWidget);

    // 4. Mascot is inside AskTutorBubble, NOT ExplanationBubble
    expect(
      find.descendant(of: find.byType(AskTutorBubble), matching: find.byType(MascotPlaceholder)),
      findsOneWidget,
    );
    expect(
      find.descendant(of: find.byType(ExplanationBubble), matching: find.byType(MascotPlaceholder)),
      findsNothing,
    );

    // 5. Tapping AskTutorBubble navigates to tutor-chat
    await tester.tap(find.byType(AskTutorBubble));
    await tester.pumpAndSettle();
    expect(navigatedToTutorChat, isTrue);
  });
}
