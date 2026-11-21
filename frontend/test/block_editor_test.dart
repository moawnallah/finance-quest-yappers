import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:finance_quest/widgets/block_editor.dart';

const ifP = Piece('if … :', 'if', 'if', 'if', cControl);
const elifP = Piece('elif … :', 'elif', 'elif', 'elif', cControl);
const elseP = Piece('else:', 'else', 'else', 'else', cControl);
const buf = Piece('save_to_buffer', 'save_to_buffer(cash)', 'a', 'line', cAction);
const pot = Piece('save_to_pot', 'save_to_pot(cash)', 'a', 'line', cAction);
Piece tok(String c) => Piece(c, c, c, 'token', cValue);

Future<(BlockProgram, BlockEditorState, List<String>)> pump(WidgetTester t) async {
  final program = BlockProgram();
  final codes = <String>[];
  final key = GlobalKey<BlockEditorState>();
  await t.pumpWidget(MaterialApp(
    home: Scaffold(
      body: BlockEditor(key: key, program: program, wide: true, onChanged: codes.add, palette: [('Control', cControl, [ifP, elifP, elseP])]),
    ),
  ));
  return (program, key.currentState!, codes);
}

void main() {
  testWidgets('tapping blocks in order builds an if/else plan', (t) async {
    final (p, s, codes) = await pump(t);
    for (final x in [ifP, tok('buffer_months'), tok('<'), tok('1000'), buf, elseP, pot]) {
      s.place(x);
      await t.pump();
    }
    expect(p.code(), 'if buffer_months < 1000:\n    save_to_buffer(cash)\nelse:\n    save_to_pot(cash)');
    expect(codes.last, p.code());
  });

  testWidgets('elif goes between the if and its else; a second else is refused', (t) async {
    final (p, s, _) = await pump(t);
    s.place(ifP);
    s.place(tok('cash'));
    s.place(buf);
    s.place(elseP);
    s.place(pot);
    s.place(elifP, at: p.root.first); // the if's gap is the anchor
    await t.pump();
    expect(p.root.map((x) => x.kind).toList(), ['if', 'elif', 'else']);
    s.place(elseP, at: p.root.first);
    await t.pump();
    expect(p.root.where((x) => x.kind == 'else').length, 1);
  });

  testWidgets('else without an if and a value outside a gap are refused', (t) async {
    final (p, s, _) = await pump(t);
    s.place(elseP);
    s.place(tok('cash'), at: Slot(p.root, 0));
    await t.pump();
    expect(p.root, isEmpty);
    expect(find.byType(SnackBar), findsOneWidget);
  });

  test('code reads back into the same blocks', () {
    const code = 'if buffer_months < 2 and not employed:\n    save_to_buffer(min(cash, 1000))\n'
        'elif card_debt > 0:\n    pay_debt(cash)\n    if cash > 500:\n        invest_in(cash, fund)\nelse:\n    save_to_pot(cash)\nmy_total += cash';
    final p = BlockProgram.parse('# a comment\n$code', (_) => cAction)!;
    expect(p.code(), code);
    expect(p.root.first.tokens, ['buffer_months', '<', '2', 'and', 'not', 'employed']);
  });

  test('code the blocks cannot show is refused, not mangled', () {
    expect(BlockProgram.parse('if cash > 1:\n  save_to_pot(cash)\n    pay_debt(cash)', (_) => cAction), isNull);
  });
}
