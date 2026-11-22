// Scratch-like block workspace for hard tasks. The blocks are the source of truth; the code the
// backend runs is generated from them (BlockProgram.code). Two ways to build, both always work:
//   - drag a block from the palette onto a slot (between lines, inside an if) or onto a gap (___);
//   - tap a slot or a gap to select it, then tap a block in the palette.
// Placed blocks can be dragged to another slot, and removed with their x.
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'common.dart';

const cControl = Color(0xFFFFAB19), cCond = Color(0xFF59C059), cMath = Color(0xFF0FBD8C),
    cValue = Color(0xFF4C97FF), cAction = Color(0xFF9966FF), cMine = Color(0xFFFF8C1A);

/// One palette entry. Statements (if/elif/else/action/line) go into slots; tokens go into a gap.
/// An action has [args]: 'amount' (a gap that takes values, numbers and maths) and/or 'asset' (a chip
/// that picks one of the task's assets), e.g. invest_in(amount, asset).
class Piece {
  final String label, code, tip, kind; // kind: if, elif, else, action, line, token
  final Color color;
  final List<String> args;
  const Piece(this.label, this.code, this.tip, this.kind, this.color, {this.args = const []});
  bool get isStatement => kind != 'token';
}

class Stmt {
  String kind; // if, elif, else, action, line
  String code; // the line itself for kind == line; the action's name for kind == action
  final List<String> tokens = []; // the condition of if / elif, or an action's amount
  final List<Stmt> body = [];
  final Color color;
  final List<String> args; // actions only: 'amount' and/or 'asset'
  String? asset; // actions with an 'asset' argument
  Stmt(this.kind, this.code, this.color, {this.args = const [], this.asset});
  bool get block => kind == 'if' || kind == 'elif' || kind == 'else';
  bool get hasGap => kind == 'if' || kind == 'elif' || (kind == 'action' && args.contains('amount'));
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

/// Tokens back to code: spaces between them, none just inside brackets.
String joinTokens(List<String> t) => t.join(' ').replaceAll('( ', '(').replaceAll(' )', ')');

class BlockProgram {
  final List<Stmt> root = [];

  static String line(Stmt s) {
    if (s.kind != 'action') return s.code;
    final parts = [
      for (final a in s.args) a == 'asset' ? (s.asset ?? '___') : (s.tokens.isEmpty ? '___' : joinTokens(s.tokens)),
    ];
    return '${s.code}(${parts.join(', ')})';
  }

  String code() {
    final out = StringBuffer();
    void emit(List<Stmt> l, int d) {
      for (final s in l) {
        final pad = '    ' * d;
        if (!s.block) {
          out.writeln('$pad${line(s)}');
        } else {
          out.writeln(s.kind == 'else' ? '${pad}else:' : '$pad${s.kind} ${s.tokens.isEmpty ? '___' : joinTokens(s.tokens)}:');
          emit(s.body, d + 1);
        }
      }
    }
    emit(root, 0);
    return out.toString().trimRight();
  }

  static final _tok = RegExp(r'\w+\([^()]*\)|\d+\.\d+|\w+|[<>]=?|==|!=|\+=|[-+*/()]|\S');
  static List<String> tokenize(String t) => _tok.allMatches(t).map((x) => x.group(0)!).where((x) => x != '___').toList();

  /// Split an argument list at top-level commas: "(a - b) / c, fund" -> ["(a - b) / c", "fund"].
  static List<String> splitArgs(String t) {
    final out = <String>[];
    var depth = 0, cur = StringBuffer();
    for (final ch in t.split('')) {
      if (ch == ',' && depth == 0) {
        out.add(cur.toString().trim());
        cur = StringBuffer();
        continue;
      }
      if (ch == '(') depth++;
      if (ch == ')') depth--;
      cur.write(ch);
    }
    if (cur.toString().trim().isNotEmpty || out.isNotEmpty) out.add(cur.toString().trim());
    return out;
  }

  /// Read code back into blocks. Returns null when it is not something the blocks can show.
  /// [actions] maps an action's name to its arguments (as in [Piece.args]), so its calls become
  /// action blocks with an amount gap and an asset chip.
  static BlockProgram? parse(String text, Color Function(String line) colorOf, {Map<String, List<String>> actions = const {}}) {
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
      final call = RegExp(r'^(\w+)\((.*)\)$').firstMatch(line);
      if (m != null || line == 'else:') {
        final s = Stmt(m?.group(1) ?? 'else', '', cControl);
        if (m != null) s.tokens.addAll(tokenize(m.group(2)!));
        stack.last.$2.add(s);
        stack.add((ind + 4, s.body));
      } else if (call != null && actions.containsKey(call.group(1))) {
        final args = actions[call.group(1)]!;
        final vals = splitArgs(call.group(2)!);
        if (vals.length != args.length) return null;
        final s = Stmt('action', call.group(1)!, cAction, args: args);
        for (var i = 0; i < args.length; i++) {
          if (args[i] == 'asset') {
            s.asset = vals[i] == '___' ? null : vals[i];
          } else {
            s.tokens.addAll(tokenize(vals[i]));
          }
        }
        stack.last.$2.add(s);
      } else {
        stack.last.$2.add(Stmt('line', line, colorOf(line)));
      }
    }
    return p;
  }
}

/// A bar that resizes the panels on either side when dragged: a visible grip, a resize cursor, and
/// green while hovered or dragged.
class ResizeHandle extends StatefulWidget {
  final Axis axis; // Axis.horizontal: a vertical bar dragged left/right; Axis.vertical: a horizontal bar dragged up/down
  final ValueChanged<double> onDrag;
  const ResizeHandle({super.key, required this.axis, required this.onDrag});
  @override
  State<ResizeHandle> createState() => _ResizeHandleState();
}

class _ResizeHandleState extends State<ResizeHandle> {
  bool _active = false;

  @override
  Widget build(BuildContext context) {
    final h = widget.axis == Axis.horizontal;
    final c = _active ? kPrimary : kBorder;
    return Semantics(
      container: true, // its own node: screen readers (and tests) find it
      label: h ? 'Drag to resize the panels left and right' : 'Drag to resize the panels up and down',
      child: MouseRegion(
        cursor: h ? SystemMouseCursors.resizeColumn : SystemMouseCursors.resizeRow,
        onEnter: (_) => setState(() => _active = true),
        onExit: (_) => setState(() => _active = false),
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onHorizontalDragStart: h ? (_) => setState(() => _active = true) : null,
          onHorizontalDragUpdate: h ? (d) => widget.onDrag(d.delta.dx) : null,
          onVerticalDragStart: h ? null : (_) => setState(() => _active = true),
          onVerticalDragUpdate: h ? null : (d) => widget.onDrag(d.delta.dy),
          child: SizedBox(
            width: h ? 12 : double.infinity,
            height: h ? double.infinity : 12,
            child: Stack(alignment: Alignment.center, children: [
              Container(width: h ? (_active ? 2 : 1) : double.infinity, height: h ? double.infinity : (_active ? 2 : 1), color: _active ? kPrimary : kLine),
              Container(
                width: h ? 8 : 48,
                height: h ? 48 : 8,
                decoration: BoxDecoration(color: kSurface, borderRadius: BorderRadius.circular(4), border: Border.all(color: c, width: 1.5)),
                child: Icon(h ? Icons.more_vert : Icons.more_horiz, size: 8, color: c),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}

class BlockEditor extends StatefulWidget {
  final BlockProgram program;
  final List<(String, Color, List<Piece>)> palette; // sections
  final ValueChanged<String> onChanged;
  final bool wide;
  final List<String> assets; // what an action's asset chip can pick
  const BlockEditor({super.key, required this.program, required this.palette, required this.onChanged, required this.wide, this.assets = const []});
  @override
  State<BlockEditor> createState() => BlockEditorState();
}

/// On touch screens an immediate drag would steal the scroll gesture: drag starts with a long press
/// there (a tap still places a block). With a mouse, dragging starts at once.
bool get _touch => defaultTargetPlatform == TargetPlatform.android || defaultTargetPlatform == TargetPlatform.iOS;

Widget _draggable({required Object data, required Widget feedback, required Widget childWhenDragging, required Widget child}) => _touch
    ? LongPressDraggable<Object>(data: data, feedback: feedback, childWhenDragging: childWhenDragging, child: child)
    : Draggable<Object>(data: data, feedback: feedback, childWhenDragging: childWhenDragging, child: child);

class BlockEditorState extends State<BlockEditor> {
  Object? _target; // a Slot, or a Stmt whose condition gap is selected
  double _paletteW = 330; // drag the bar between palette and workspace to change it
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
      if (s == null || !s.hasGap) {
        _hint('Values, comparisons, numbers and maths go in a gap (___): the condition of an if or elif, or the amount of an action. Tap the gap first, or drag the block onto it.');
        return;
      }
      s.tokens.add(p.code.trim());
      _target = s;
      _changed();
      return;
    }
    final stmt = Stmt(p.kind, p.code, p.color, args: p.args,
        asset: p.args.contains('asset') && widget.assets.isNotEmpty ? widget.assets.first : null);
    if (p.args.contains('amount')) stmt.tokens.add('cash'); // a start: tap it to remove, or add maths after it
    if (p.kind == 'elif' || p.kind == 'else') {
      // Goes right after the if/elif chain it belongs to: the one whose gap or body is selected,
      // or the one just before the slot.
      Stmt? anchor = at is Stmt ? at : at is Slot ? _owner(at.list) : null;
      if (at is Slot && at.index > 0 && (at.list[at.index - 1].kind == 'if' || at.list[at.index - 1].kind == 'elif')) anchor = at.list[at.index - 1];
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
    return LayoutBuilder(builder: (context, c) {
      final w = _paletteW.clamp(200.0, (c.maxWidth - 300).clamp(200.0, 700.0));
      return Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        SizedBox(width: w, child: palette),
        ResizeHandle(axis: Axis.horizontal, onDrag: (d) => setState(() => _paletteW = w + d)),
        Expanded(child: work),
      ]);
    });
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
          child: _draggable(
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
        label: 'Gap: put a condition or an amount here',
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
      : RegExp(r'^-?\d').hasMatch(t) || RegExp(r'^[-+*/()]$|^(min|max)\(').hasMatch(t)
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

  void setAsset(Stmt s, String asset) {
    s.asset = asset;
    _changed();
  }

  void removeToken(Stmt s, int i) {
    s.tokens.removeAt(i);
    _target = s;
    _changed();
  }

  /// The asset an action uses: tap to pick another of the task's assets.
  Widget _assetChip(Stmt s) => Semantics(
        button: true,
        label: 'Asset: ${s.asset ?? 'choose'}',
        excludeSemantics: true,
        child: PopupMenuButton<String>(
          tooltip: 'Choose the asset',
          onSelected: (v) => setAsset(s, v),
          itemBuilder: (_) => [for (final a in widget.assets) PopupMenuItem(value: a, child: Text(a))],
          child: Container(
            padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(999), border: Border.all(color: Colors.black26)),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              Text(s.asset ?? 'asset', style: GoogleFonts.robotoMono(fontSize: 12, fontWeight: FontWeight.w800, color: cAction)),
              Icon(Icons.arrow_drop_down, size: 16, color: cAction),
            ]),
          ),
        ),
      );

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
            Text(s.kind == 'line' || s.kind == 'action' ? (s.kind == 'action' ? '${s.code}(' : s.code) : s.kind,
                style: GoogleFonts.robotoMono(fontSize: 13, fontWeight: FontWeight.w800, color: Colors.white)),
            if (s.kind == 'action') ...[
              for (final (n, a) in s.args.indexed) ...[
                if (n > 0) Text(',', style: GoogleFonts.robotoMono(fontSize: 13, fontWeight: FontWeight.w800, color: Colors.white)),
                if (a == 'amount') ...[for (var i = 0; i < s.tokens.length; i++) _token(s, i), _gap(s)] else _assetChip(s),
              ],
              Text(')', style: GoogleFonts.robotoMono(fontSize: 13, fontWeight: FontWeight.w800, color: Colors.white)),
            ],
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
    final draggable = _draggable(
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
