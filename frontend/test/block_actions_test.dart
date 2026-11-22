// Both reference programs of the hard tasks can be built from blocks alone (no typing), and the code
// the blocks make matches the reference exactly.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:finance_quest/widgets/block_editor.dart';

const ifP = Piece('if … :', 'if', 'if', 'if', cControl);
const elifP = Piece('elif … :', 'elif', 'elif', 'elif', cControl);
const elseP = Piece('else:', 'else', 'else', 'else', cControl);
Piece act(String name, List<String> args) => Piece(name, name, name, 'action', cAction, args: args);
Piece tok(String c) => Piece(c, c, c, 'token', cValue);

Future<(BlockProgram, BlockEditorState)> pump(WidgetTester t, List<String> assets) async {
  final program = BlockProgram();
  final key = GlobalKey<BlockEditorState>();
  await t.pumpWidget(MaterialApp(home: Scaffold(body: BlockEditor(key: key, program: program, wide: true, assets: assets, onChanged: (_) {},
      palette: [('Control', cControl, [ifP])]))));
  return (program, key.currentState!);
}

const p1 = '''if buffer_months < 2:
    save_to_buffer(cash)
else:
    save_to_pot((next_bill - pot) / months_to_next_bill)
    if card_debt > 0:
        pay_debt(cash)
    elif buffer_months < 3:
        save_to_buffer(cash)
    else:
        invest_in(cash * 0.7, fund)
        invest_in(cash, bond)''';

const p4 = '''if shares_weight < target_shares:
    invest_in(cash, shares)
else:
    invest_in(cash, bonds)
if drift > 0.05 and drift * invested > 1000:
    rebalance()''';

void main() {
  testWidgets('P1 reference built from blocks only', (t) async {
    final (p, s) = await pump(t, ['fund', 'bond', 'crocotech']);
    void toks(Stmt at, String ts) => [for (final x in ts.split(' ')) s.place(tok(x), at: at)];
    s.place(ifP);
    final if1 = p.root[0];
    toks(if1, 'buffer_months < 2');
    s.place(act('save_to_buffer', ['amount']));
    s.place(elseP);
    final else1 = p.root[1];
    s.place(act('save_to_pot', ['amount']));
    final pot = else1.body[0];
    s.removeToken(pot, 0); // drop the starting "cash"
    toks(pot, '( next_bill - pot ) / months_to_next_bill');
    s.place(ifP, at: Slot(else1.body, 1));
    final if2 = else1.body[1];
    toks(if2, 'card_debt > 0');
    s.place(act('pay_debt', ['amount']));
    s.place(elifP, at: if2);
    final elif2 = else1.body[2];
    toks(elif2, 'buffer_months < 3');
    s.place(act('save_to_buffer', ['amount']));
    s.place(elseP, at: elif2);
    final else2 = else1.body[3];
    s.place(act('invest_in', ['amount', 'asset']), at: Slot(else2.body, 0));
    toks(else2.body[0], '* 0.7');
    s.place(act('invest_in', ['amount', 'asset']), at: Slot(else2.body, 1));
    s.setAsset(else2.body[1], 'bond');
    await t.pump();
    expect(p.code(), p1);
  });

  testWidgets('P4 reference built from blocks only, asset picked in the chip menu', (t) async {
    final (p, s) = await pump(t, ['shares', 'bonds']);
    void toks(Stmt at, String ts) => [for (final x in ts.split(' ')) s.place(tok(x), at: at)];
    s.place(ifP);
    toks(p.root[0], 'shares_weight < target_shares');
    s.place(act('invest_in', ['amount', 'asset']));
    s.place(elseP);
    s.place(act('invest_in', ['amount', 'asset']));
    await t.pump();
    // pick "bonds" for the second invest_in through its chip, like a learner would
    await t.tap(find.text('shares').last);
    await t.pumpAndSettle();
    await t.tap(find.text('bonds').last);
    await t.pumpAndSettle();
    s.place(ifP, at: Slot(p.root, 2));
    toks(p.root[2], 'drift > 0.05 and drift * invested > 1000');
    s.place(act('rebalance', []));
    await t.pump();
    expect(p.code(), p4);
  });

  test('both references read back into the same blocks (Text <-> Blocks)', () {
    final actions = {'save_to_buffer': ['amount'], 'save_to_pot': ['amount'], 'pay_debt': ['amount'], 'invest_in': ['amount', 'asset'], 'rebalance': <String>[]};
    for (final ref in [p1, p4]) {
      final b = BlockProgram.parse(ref, (_) => cAction, actions: actions)!;
      expect(b.code(), ref);
    }
    final b = BlockProgram.parse(p1, (_) => cAction, actions: actions)!;
    final pot = b.root[1].body[0];
    expect(pot.kind, 'action');
    expect(pot.tokens, ['(', 'next_bill', '-', 'pot', ')', '/', 'months_to_next_bill']);
    expect(b.root[1].body[3].body[1].asset, 'bond');
  });
}
