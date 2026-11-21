// Drawn tests opened directly, without the lesson cards:
// - the quick check (test-out) from the Path tab: 2 of the node's check items, both right = node done;
// - the prerequisite check from the "Start this mission?" pop-up: items from earlier missions.
// Returns whether it was passed (null when it could not start).

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import 'task_screen.dart';

Future<bool?> runDrawnTest(BuildContext context, String nodeId, {required bool testOut, String? title}) async {
  final s = context.read<AppState>();
  final path = testOut ? 'test-out' : 'prerequisite-test';
  final kind = testOut ? 'test_out' : 'prerequisite';
  try {
    final test = await s.api.drawnTest(s.profile.name, nodeId, path);
    final ids = [for (final i in test['items'] as List) i['id'] as String];
    if (ids.isEmpty) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('No questions to draw for this mission yet.')));
      }
      return null;
    }
    if (!context.mounted) return null;
    await context.push('/skill-run',
        extra: TaskRun(title: title ?? (testOut ? 'Quick check' : 'Prerequisite check'), taskIds: ids, context: kind, forNode: nodeId));
    final st = (await s.api.skill(s.profile.name, nodeId))['status'] as Map;
    s.loadSkills(); // progress may have changed
    return (st[kind] as Map?)?['passed'] == true;
  } catch (e) {
    if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    return null;
  }
}
