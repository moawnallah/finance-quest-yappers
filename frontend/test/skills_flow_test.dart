// Runs the Skills task flow against responses captured from the real backend
// (test/fixtures/api.json): every easy item kind, then the day-X chart task.

import 'dart:convert';
import 'dart:io';

import 'package:finance_quest/data/api.dart';
import 'package:finance_quest/data/app_state.dart';
import 'package:finance_quest/screens/skills_screen.dart';
import 'package:finance_quest/screens/task_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  final fx = jsonDecode(File('test/fixtures/api.json').readAsStringSync()) as Map<String, dynamic>;
  final calls = <String>[];
  final client = MockClient((req) async {
    final key = '${req.method} ${req.url.path}';
    calls.add(key);
    if (!fx.containsKey(key)) return http.Response('{"error":{"code":"not_found","message":"$key"}}', 404);
    return http.Response(jsonEncode(fx[key]), 200, headers: {'content-type': 'application/json'});
  });

  Future<AppState> pump(WidgetTester tester, Widget child) async {
    SharedPreferences.setMockInitialValues({});
    tester.view.physicalSize = Size(1200, 6000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    final state = AppState()..api = Api(client: client, baseUrl: 'http://test');
    final router = GoRouter(routes: [GoRoute(path: '/', builder: (_, __) => child)]);
    await tester.pumpWidget(ChangeNotifierProvider.value(value: state, child: MaterialApp.router(routerConfig: router)));
    await tester.pumpAndSettle();
    return state;
  }

  Future<void> tapText(WidgetTester tester, String text) async {
    final f = find.textContaining(text).first;
    await tester.ensureVisible(f);
    await tester.tap(f);
    await tester.pumpAndSettle();
  }

  Future<void> checkAndNext(WidgetTester tester, String expected) async {
    await tapText(tester, 'Check my answer');
    expect(find.textContaining(expected), findsWidgets);
    await tapText(tester, 'Next');
  }

  testWidgets('skills list shows every node with progress', (tester) async {
    await pump(tester, SkillsScreen());
    expect(find.textContaining('skills complete'), findsOneWidget);
    expect(find.text('What moves a price'), findsOneWidget);
    expect(calls, containsAll(['POST /auth/session', 'GET /skills']));
  });

  testWidgets('task run: all easy kinds, then the day-X chart task', (tester) async {
    final ids = (fx['_order'] as List).cast<String>();
    final state = await pump(tester, TaskRunScreen(run: TaskRun(title: 'Test run', taskIds: ids)));
    final opt = (String id, int i) => (fx['GET /tasks/$id']['task']['options'] as List)[i] as String;

    // single
    await tapText(tester, opt(ids[0], 0));
    await tapText(tester, '4 · Sure');
    await checkAndNext(tester, 'Correct');
    // multi
    await tapText(tester, opt(ids[1], 0));
    await tapText(tester, '4 · Sure');
    await checkAndNext(tester, '%');
    // true / false
    await tapText(tester, 'True');
    await tapText(tester, '4 · Sure');
    await checkAndNext(tester, '%');
    // numeric (slider)
    await tester.ensureVisible(find.byType(Slider));
    await tester.tap(find.byType(Slider));
    await tester.pumpAndSettle();
    await tapText(tester, '4 · Sure');
    await tapText(tester, 'Check my answer');
    expect(find.textContaining('Answer:'), findsOneWidget);
    await tapText(tester, 'Next');
    // reflection: no confidence, no score
    expect(find.text('How sure are you?'), findsNothing);
    await tapText(tester, opt(ids[4], 0));
    await checkAndNext(tester, 'No right or wrong here');
    // medium day X
    expect(find.text('Synthetic data'), findsOneWidget);
    await tapText(tester, 'Down');
    final boxes = (fx['GET /tasks/d1.m1']['task']['reasons']['boxes'] as List).cast<Map<String, dynamic>>();
    await tapText(tester, boxes.firstWhere((b) => b['id'] == 'guidance')['text'] as String);
    await tapText(tester, boxes.firstWhere((b) => b['id'] == 'priced_in')['text'] as String);
    await tapText(tester, '3 · Fairly');
    await tapText(tester, 'Check my answer');
    expect(find.textContaining('What happened: down'), findsOneWidget);
    expect(find.textContaining('score your reasons'), findsOneWidget);
    expect(find.text('Strong reason'), findsWidgets);
    await tapText(tester, 'Finish');
    expect(find.text('Back to the skill'), findsOneWidget);
    expect(state.xp, greaterThan(0));
    expect(calls.where((c) => c.endsWith('/attempts')).length, 6);
  });
}
