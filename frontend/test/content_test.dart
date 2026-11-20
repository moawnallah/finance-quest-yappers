// Checks that the bundled content parses and is consistent, so a bad edit to
// assets/roadmap.json or assets/eu_benchmark.json fails before it ships.

import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:finance_quest/models/content.dart';

void main() {
  test('roadmap.json parses and every question is well formed', () {
    final rm = Roadmap.fromJson(jsonDecode(File('assets/roadmap.json').readAsStringSync()));
    expect(rm.slices.length, 13);
    for (final s in rm.slices) {
      final ids = s.nodes.map((n) => n.id).toSet();
      for (final n in s.nodes) {
        expect(n.after.every(ids.contains), isTrue, reason: '${n.id} points to a missing node');
        for (final q in n.questions) {
          expect(q.options, isNotEmpty, reason: q.id);
          if (q.isScored) expect(q.answer! < q.options.length, isTrue, reason: q.id);
        }
      }
    }
  });

  test('eu_benchmark.json has 5 questions and the score bands', () {
    final b = jsonDecode(File('assets/eu_benchmark.json').readAsStringSync());
    expect((b['quiz'] as List).length, 5);
    expect(b['score_bands'].keys, containsAll(['high_4_or_5_correct', 'medium_2_or_3_correct', 'low_0_or_1_correct']));
  });
}
