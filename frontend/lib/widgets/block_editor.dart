// Scratch-like block workspace for hard tasks. The blocks are the source of truth; the code the
// backend runs is generated from them (BlockProgram.code). Two ways to build, both always work:
//   - drag a block from the palette onto a slot (between lines, inside an if) or onto a gap (___);
//   - tap a slot or a gap to select it, then tap a block in the palette.
// Placed blocks can be dragged to another slot, and removed with their x.
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'common.dart';

const cControl = Color(0xFFFFAB19), cCond = Color(0xFF59C059), cMath = Color(0xFF0FBD8C),
    cValue = Color(0xFF4C97FF), cAction = Color(0xFF9966FF), cMine = Color(0xFFFF8C1A);

/// One palette entry. Statements (if/elif/else/line) go into slots; tokens go into a condition gap.
class Piece {
  final String label, code, tip, kind; // kind: if, elif, else, line, token
  final Color color;
  const Piece(this.label, this.code, this.tip, this.kind, this.color);
  bool get isStatement => kind != 'token';
}

class Stmt {
  String kind; // if, elif, else, line
  String code; // the line itself for kind == line
  final List<String> tokens = []; // the condition of if / elif
  final List<Stmt> body = [];
  final Color color;
  Stmt(this.kind, this.code, this.color);
  bool get block => kind != 'line';
}

/// A place a statement can go: index [index] of list [list].
class Slot {
  final List<Stmt> list;
  final int index;
  Slot(this.list, this.index);
  @override
  bool operator ==(Object o) => o is Slot && identical(o.list, list) && o.index == index;
  @override
  int get hashCode => Object.hash(identityHashCode(list), index);
}

class BlockProgram {
  final List<Stmt> root = [];

  String code() {
    final out = StringBuffer();
    void emit(List<Stmt> l, int d) {
      for (final s in l) {
        final pad = '    ' * d;
        if (s.kind == 'line') {
          out.writeln('$pad${s.code}');
        } else {
          out.writeln(s.kind == 'else' ? '${pad}else:' : '$pad${s.kind} ${s.tokens.isEmpty ? '___' : s.tokens.join(' ')}:');
          emit(s.body, d + 1);
        }
      }
    }
    emit(root, 0);
    return out.toString().trimRight();
  }

  static final _tok = RegExp(r'\w+\([^)]*\)|[<>]=?|==|!=|\+=|[-+*/]|\S+');

  /// Read code back into blocks. Returns null when it is not something the blocks can show.
  static BlockProgram? parse(String text, Color Function(String line) colorOf) {
    final p = BlockProgram();
    final stack = <(int, List<Stmt>)>[(0, p.root)];
    for (final raw in text.split('\n')) {
      if (raw.trim().isEmpty || raw.trimLeft().startsWith('#')) continue;
      final ind = raw.length - raw.trimLeft().length, line = raw.trim();
      while (stack.length > 1 && ind < stack.last.$1) {
        stack.removeLast();
      }
      if (ind != stack.last.$1) return null;
      final m = RegExp(r'^(if|elif)\s+(.*):$').firstMatch(line);
      if (m != null || line == 'else:') {
        final s = Stmt(m?.group(1) ?? 'else', '', cControl);
        if (m != null) s.tokens.addAll(_tok.allMatches(m.group(2)!).map((x) => x.group(0)!).where((x) => x != '___'));
        stack.last.$2.add(s);
        stack.add((ind + 4, s.body));
      } else {
        stack.last.$2.add(Stmt('line', line, colorOf(line)));
      }
    }
    return p;
  }
}

class BlockEditor extends StatefulWidget {
  final BlockProgram program;
  final List<(String, Color, List<Piece>)> palette; // sections
  final ValueChanged<String> onChanged;
  final bool wide;
  const BlockEditor({super.key, required this.program, required this.palette, required this.onChanged, required this.wide});
  @override
  State<BlockEditor> createState() => BlockEditorState();
}

class BlockEditorState extends State<BlockEditor> {
  Object? _target; // a Slot, or a Stmt whose condition gap is selected
  Object? _hover;

  List<Stmt> get _root => widget.program.root;

  void _changed() {
    setState(() {});
    widget.onChanged(widget.program.code());
  }

  // ---- where things are
  (List<Stmt>, int)? _find(Stmt s, [List<Stmt>? l]) {
    l ??= _root;
    for (var i = 0; i < l.length; i++) {
      if (identical(l[i], s)) return (l, i);
      final r = _find(s, l[i].body);
      if (r != null) return r;
    }
    return null;
  }

  /// The if/elif that owns a list (the list is its body), or null for the top level.
  Stmt? _owner(List<Stmt> list, [List<Stmt>? l]) {
    l ??= _root;
    for (final s in l) {
      if (identical(s.body, list)) return s;
      final r = _owner(list, s.body);
      if (r != null) return r;
    }
    return null;
  }

  void _hint(String t) => ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(t)));

  // ---- placing
  /// Put a palette piece at the target (tap) or at [at] (drop).
  void place(Piece p, {Object? at}) {
    at ??= _target ?? Slot(_root, _root.length);
    if (!p.isStatement) {
      final s = at is Stmt ? at : null;
      if (s == null || s.kind == 'else') {
        _hint('Values, comparisons and numbers go in the gap (___) of an if or elif. Tap the gap first, or drag the block onto it.');
        return;
      }
      s.tokens.add(p.code.trim());
      _target = s;
      _changed();
      return;
    }
    final stmt = Stmt(p.kind, p.code, p.color);
    if (p.kind == 'elif' || p.kind == 'else') {
      // Goes right after the if/elif chain it belongs to: the one whose gap or body is selected,
      // or the one just before the slot.
      Stmt? anchor = at is Stmt ? at : at is Slot ? _owner(at.list) : null;
      if (at is Slot && at.index > 0 && at.list[at.index - 1].kind != 'line' && at.list[at.index - 1].kind != 'else') anchor = at.list[at.index - 1];
      if (anchor == null || anchor.kind == 'else') {
        _hint('"${p.label}" belongs after an if. Add an if first, then tap ${p.label}.');
        return;
      }
      final (list, i) = _find(anchor)!;
      var j = i + 1;
      while (j < list.length && list[j].kind == 'elif') {
        j++;
      }
      if (p.kind == 'else' && j < list.length && list[j].kind == 'else') {
        _hint('This if already has an else.');
        return;
      }
      list.insert(j, stmt);
    } else {
      final slot = at is Stmt ? Slot(at.body, at.body.length) : at as Slot; // a gap selected: the line goes inside
      slot.list.insert(slot.index.clamp(0, slot.list.length), stmt);
    }
    // What comes next: an if fills its gap, a block fills its body, a line keeps adding below itself.
    if (stmt.kind == 'if' || stmt.kind == 'elif') {
      _target = stmt;
    } else if (stmt.kind == 'else') {
      _target = Slot(stmt.body, 0);
    } else {
      final (list, i) = _find(stmt)!;
      _target = Slot(list, i + 1);
    }
    _changed();
  }

  void _move(Stmt s, Slot to) {
    if (_inside(to.list, s)) return; // cannot drop a block into itself
    final (from, i) = _find(s)!;
    var idx = to.index;
    if (identical(from, to.list) && i < idx) idx--;
    from.removeAt(i);
    to.list.insert(idx.clamp(0, to.list.length), s);
    _target = Slot(to.list, idx + 1);
    _changed();
  }

  bool _inside(List<Stmt> list, Stmt s) => identical(list, s.body) || s.body.any((c) => _inside(list, c));

  void _remove(Stmt s) {
    final (list, i) = _find(s)!;
    list.removeAt(i);
    _target = Slot(list, i);
    _changed();
  }

  // ---- widgets
  @override
  Widget build(BuildContext context) {
    final palette = _palette();
    final work = _workspace();
    if (!widget.wide) return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [SizedBox(height: 230, child: palette), Divider(height: 1, color: kLine), Expanded(child: work)]);
    return Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [SizedBox(width: 330, child: palette), VerticalDivider(width: 1, color: kLine), Expanded(child: work)]);
  }

  Widget _palette() => ListView(padding: EdgeInsets.all(10), children: [
        for (final (title, color, pieces) in widget.palette)
          Padding(
            padding: EdgeInsets.only(bottom: 10),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Container(width: 10, height: 10, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
                SizedBox(width: 6),
                Text(title, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: kMuted)),
              ]),
              SizedBox(height: 6),
              Wrap(spacing: 6, runSpacing: 6, children: [for (final p in pieces) _paletteBlock(p)]),
            ]),
          ),
      ]);

  Widget _chipOf(String label, Color c, {bool small = false}) => Container(
        padding: EdgeInsets.symmetric(horizontal: small ? 8 : 10, vertical: small ? 4 : 7),
        decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(8), border: Border.all(color: Colors.black.withValues(alpha: .15))),
        child: Text(label, style: GoogleFonts.robotoMono(fontSize: small ? 12 : 13, fontWeight: FontWeight.w700, color: Colors.white)),
      );

  Widget _paletteBlock(Piece p) => Tooltip(
        message: p.tip,
        child: Semantics(
          button: true,
          label: '${p.tip}\n${p.label}',
          excludeSemantics: true,
          child: Draggable<Object>(
            data: p,
            feedback: Material(color: Colors.transparent, child: _chipOf(p.label, p.color)),
            childWhenDragging: Opacity(opacity: .4, child: _chipOf(p.label, p.color)),
            child: MouseRegion(cursor: SystemMouseCursors.grab, child: GestureDetector(onTap: () => place(p), child: _chipOf(p.label, p.color))),
          ),
        ),
      );

  Widget _workspace() => Container(
        color: appDark ? Color(0xFF14171F) : Color(0xFFF7F8F5),
        child: ListView(padding: EdgeInsets.fromLTRB(14, 12, 14, 40), children: [
          if (_root.isEmpty)
            Padding(
              padding: EdgeInsets.only(bottom: 8),
              child: Text('Start with an orange "if" block: drag it here, or tap it.', style: TextStyle(color: kMuted)),
            ),
          ..._list(_root),
        ]),
      );

  List<Widget> _list(List<Stmt> l) => [
        for (var i = 0; i < l.length; i++) ...[_slot(Slot(l, i)), _stmt(l[i])],
        _slot(Slot(l, l.length), last: true, hint: l.isEmpty && !identical(l, _root) ? 'Put an action inside: drop it here, or tap here then tap it' : null),
      ];

  Widget _slot(Slot s, {bool last = false, String? hint}) {
    final sel = _target == s, hov = _hover == s, big = sel || hov || hint != null;
    return DragTarget<Object>(
      onWillAcceptWithDetails: (d) {
        final ok = d.data is Stmt || (d.data is Piece && (d.data as Piece).isStatement);
        if (ok) setState(() => _hover = s);
        return ok;
      },
      onLeave: (_) => setState(() => _hover = null),
      onAcceptWithDetails: (d) {
        _hover = null;
        d.data is Stmt ? _move(d.data as Stmt, s) : place(d.data as Piece, at: s);
      },
      builder: (_, __, ___) => Semantics(
        button: true,
        label: 'Slot: put a line here',
        child: GestureDetector(
          onTap: () => setState(() => _target = s),
          child: MouseRegion(
            cursor: SystemMouseCursors.click,
            child: AnimatedContainer(
              duration: Duration(milliseconds: 120),
              height: big ? 28 : (last ? 18 : 10),
              margin: EdgeInsets.symmetric(vertical: 1),
              alignment: Alignment.centerLeft,
              decoration: BoxDecoration(
                color: sel || hov ? kPrimary.withValues(alpha: .12) : Colors.transparent,
                borderRadius: BorderRadius.circular(6),
                border: sel || hov ? Border.all(color: kPrimary, width: 1.5) : hint != null ? Border.all(color: kBorder) : null,
              ),
              padding: EdgeInsets.only(left: 8),
              child: big ? Text(hov ? 'Drop here' : sel ? 'Next line goes here' : hint!, style: TextStyle(fontSize: 11, color: sel || hov ? kPrimaryText : kMuted, fontWeight: FontWeight.w700)) : null,
            ),
          ),
        ),
      ),
    );
  }

  Widget _gap(Stmt s) {
    final sel = _target == s, hov = _hover == s;
    return DragTarget<Object>(
      onWillAcceptWithDetails: (d) {
        final ok = d.data is Piece && !(d.data as Piece).isStatement;
        if (ok) setState(() => _hover = s);
        return ok;
      },
      onLeave: (_) => setState(() => _hover = null),
      onAcceptWithDetails: (d) {
        _hover = null;
        place(d.data as Piece, at: s);
      },
      builder: (_, __, ___) => Semantics(
        button: true,
        label: 'Gap: put a condition here',
        child: GestureDetector(
          onTap: () => setState(() => _target = s),
          child: MouseRegion(
            cursor: SystemMouseCursors.click,
            child: Container(
              padding: EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: sel || hov ? Colors.white : Colors.white.withValues(alpha: .55),
                borderRadius: BorderRadius.circular(999),
                border: Border.all(color: sel || hov ? kPrimary : Colors.black26, width: sel || hov ? 2 : 1),
              ),
              child: Text('___', style: GoogleFonts.robotoMono(fontSize: 12, fontWeight: FontWeight.w700, color: Colors.black54)),
            ),
          ),
        ),
      ),
    );
  }

  Color _tokenColor(String t) => RegExp(r'^[<>]=?$|^(and|or|not|==|!=)$').hasMatch(t)
      ? cCond
      : RegExp(r'^-?\d').hasMatch(t) || RegExp(r'^[-+*/]$|^(min|max)\(').hasMatch(t)
          ? cMath
          : cValue;

  Widget _token(Stmt s, int i) {
    final t = s.tokens[i];
    return GestureDetector(
      onTap: () => _editToken(s, i),
      child: MouseRegion(cursor: SystemMouseCursors.click, child: Tooltip(message: 'Tap to change or remove', child: _chipOf(t, _tokenColor(t), small: true))),
    );
  }

  Future<void> _editToken(Stmt s, int i) async {
    final t = s.tokens[i];
    final number = RegExp(r'^-?\d+(\.\d+)?$').hasMatch(t);
    final ctl = TextEditingController(text: t);
    final r = await showDialog<String>(
      context: context,
      builder: (d) => AlertDialog(
        title: Text(number ? 'Change the number' : 'Remove "$t"?'),
        content: number
            ? TextField(controller: ctl, autofocus: true, keyboardType: TextInputType.number, onSubmitted: (v) => Navigator.pop(d, v))
            : null,
        actions: [
          TextButton(onPressed: () => Navigator.pop(d, ''), child: Text('Remove')),
          if (number) FilledButton(onPressed: () => Navigator.pop(d, ctl.text), child: Text('Save')) else TextButton(onPressed: () => Navigator.pop(d), child: Text('Keep')),
        ],
      ),
    );
    if (r == null) return;
    if (r.isEmpty) {
      s.tokens.removeAt(i);
    } else if (RegExp(r'^-?\d+(\.\d+)?$').hasMatch(r.trim())) {
      s.tokens[i] = r.trim();
    }
    _target = s;
    _changed();
  }

  Widget _stmt(Stmt s) {
    final head = Container(
      padding: EdgeInsets.fromLTRB(10, 6, 4, 6),
      decoration: BoxDecoration(
        color: s.color,
        borderRadius: s.block ? BorderRadius.only(topLeft: Radius.circular(8), topRight: Radius.circular(8), bottomRight: Radius.circular(8)) : BorderRadius.circular(8),
        border: Border.all(color: Colors.black.withValues(alpha: .15)),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(Icons.drag_indicator, size: 16, color: Colors.white70),
        SizedBox(width: 4),
        Flexible(
          child: Wrap(spacing: 6, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
            Text(s.kind == 'line' ? s.code : s.kind, style: GoogleFonts.robotoMono(fontSize: 13, fontWeight: FontWeight.w800, color: Colors.white)),
            if (s.kind == 'if' || s.kind == 'elif') ...[
              for (var i = 0; i < s.tokens.length; i++) _token(s, i),
              _gap(s),
              Text(':', style: GoogleFonts.robotoMono(fontSize: 13, fontWeight: FontWeight.w800, color: Colors.white)),
            ],
            if (s.kind == 'else') Text(':', style: GoogleFonts.robotoMono(fontSize: 13, fontWeight: FontWeight.w800, color: Colors.white)),
          ]),
        ),
        IconButton(
          tooltip: 'Remove this block',
          visualDensity: VisualDensity.compact,
          iconSize: 16,
          icon: Icon(Icons.close, color: Colors.white),
          onPressed: () => _remove(s),
        ),
      ]),
    );
    final draggable = Draggable<Object>(
      data: s,
      feedback: Material(color: Colors.transparent, child: Opacity(opacity: .85, child: head)),
      childWhenDragging: Opacity(opacity: .3, child: head),
      child: MouseRegion(cursor: SystemMouseCursors.grab, child: head),
    );
    if (!s.block) return Align(alignment: Alignment.centerLeft, child: draggable);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Align(alignment: Alignment.centerLeft, child: draggable),
      IntrinsicHeight(
        child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Container(width: 14, decoration: BoxDecoration(color: s.color, borderRadius: BorderRadius.only(bottomLeft: Radius.circular(8)))),
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(left: 8),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                ..._list(s.body),
              ]),
            ),
          ),
        ]),
      ),
      Container(width: 60, height: 8, decoration: BoxDecoration(color: s.color, borderRadius: BorderRadius.only(bottomLeft: Radius.circular(8), bottomRight: Radius.circular(8)))),
    ]);
  }
}
