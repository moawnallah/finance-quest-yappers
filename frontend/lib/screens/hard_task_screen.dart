// Hard task (experimental): write a plan as code and test it.
// Side panel: the task and its public tests. Main panel: the code. Lower panel:
// "Run tests" runs the public tests only (nothing is scored). "Submit" runs
// everything, including the hidden events and the futures, and shows the real
// result. Backend: GET /tasks/{id} (code panel data), POST /tasks/{id}/run,
// POST /tasks/{id}/attempts with {"code": ...} (backend/data/hard/text.py).

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../data/sfx.dart';
import '../widgets/common.dart';
import 'skills_screen.dart' show ErrorPanel;

class HardTaskScreen extends StatefulWidget {
  final String taskId;
  HardTaskScreen({super.key, required this.taskId});
  @override
  State<HardTaskScreen> createState() => _HardTaskScreenState();
}

class _HardTaskScreenState extends State<HardTaskScreen> with SingleTickerProviderStateMixin {
  late final TabController _tabs = TabController(length: 2, vsync: this); // Blocks | Test results
  final _code = TextEditingController();
  Map<String, dynamic>? _task;
  String? _loadError;
  Map<String, dynamic>? _run; // last public run
  Map<String, dynamic>? _result; // the submitted result
  String? _error; // code problem from the backend (line numbers)
  bool _busy = false;
  final _started = DateTime.now();

  @override
  void initState() {
    super.initState();
    _load();
    WidgetsBinding.instance.addPostFrameCallback((_) => _smallScreenNotice());
  }

  static const _largeScreen = 'This task can take a while and works best on a large screen (laptop or tablet).';

  Future<void> _smallScreenNotice() async {
    if (!mounted || MediaQuery.sizeOf(context).width >= 1000) return;
    final go = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (d) => AlertDialog(
        title: Text('Best on a large screen'),
        content: Text(_largeScreen),
        actions: [
          TextButton(onPressed: () => Navigator.pop(d, false), child: Text('Back')),
          FilledButton(style: FilledButton.styleFrom(minimumSize: Size(120, 44)), onPressed: () => Navigator.pop(d, true), child: Text('Continue anyway')),
        ],
      ),
    );
    if (go != true && mounted) context.pop();
  }

  @override
  void dispose() {
    _code.dispose();
    _tabs.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final s = context.read<AppState>();
    try {
      final t = await s.api.task(s.profile.name, widget.taskId);
      final task = Map<String, dynamic>.from(t['task'] as Map);
      _code.text = (task['code']?['starter'] as String?) ?? '';
      setState(() => _task = task);
    } catch (e) {
      setState(() => _loadError = '$e');
    }
  }

  Map<String, dynamic> get _panel => Map<String, dynamic>.from(_task?['code'] as Map? ?? {});

  Future<void> _runTests() async {
    final s = context.read<AppState>();
    setState(() { _busy = true; _error = null; });
    try {
      final r = await s.api.runHard(s.profile.name, widget.taskId, _code.text);
      r['required_passed'] == true ? Sfx.correct() : Sfx.wrong();
      setState(() => _run = r);
      _tabs.animateTo(1);
    } catch (e) {
      Sfx.wrong();
      setState(() { _error = '$e'; _run = null; });
      _tabs.animateTo(1);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _submit() async {
    final s = context.read<AppState>();
    setState(() { _busy = true; _error = null; });
    try {
      final r = await s.api.submit(s.profile.name, widget.taskId, response: {'code': _code.text}, startedAt: _started);
      s.syncScales((r['scales_total'] as num?)?.toInt());
      r['accepted'] == true ? Sfx.correct() : Sfx.wrong();
      setState(() => _result = r);
      if (mounted) _showResult(r);
    } catch (e) {
      Sfx.wrong();
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loadError != null) {
      return Scaffold(appBar: AppBar(title: Text('Hard task')), body: Padding(padding: EdgeInsets.all(20), child: ErrorPanel(message: _loadError!, onRetry: () { setState(() => _loadError = null); _load(); })));
    }
    if (_task == null) return Scaffold(appBar: AppBar(title: Text('Hard task')), body: Center(child: CircularProgressIndicator()));
    final wide = MediaQuery.sizeOf(context).width >= 1000;
    final actions = [
      OutlinedButton.icon(
        style: OutlinedButton.styleFrom(minimumSize: Size(120, 44)),
        onPressed: _busy ? null : _runTests,
        icon: Icon(Icons.play_arrow_rounded),
        label: Text('Run tests'),
      ),
      SizedBox(width: 8),
      FilledButton.icon(
        style: FilledButton.styleFrom(minimumSize: Size(120, 44)),
        onPressed: _busy ? null : _confirmSubmit,
        icon: Icon(Icons.send_rounded),
        label: Text('Submit'),
      ),
    ];
    return Scaffold(
      appBar: AppBar(
        title: Row(children: [
          Flexible(child: Text('Hard task', overflow: TextOverflow.ellipsis)),
          SizedBox(width: 8),
          _tag('Experimental'),
        ]),
        actions: [
          IconButton(tooltip: 'Start over', icon: Icon(Icons.restart_alt), onPressed: _busy ? null : () => setState(() { _code.text = _panel['starter'] as String? ?? ''; _run = null; _error = null; })),
          if (wide) ...actions,
          SizedBox(width: 12),
        ],
      ),
      body: wide
          ? Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              SizedBox(width: 360, child: _side()),
              VerticalDivider(width: 1, color: kLine),
              Expanded(
                child: Column(children: [
                  Expanded(child: Padding(padding: EdgeInsets.fromLTRB(16, 12, 16, 8), child: _editor(expand: true))),
                  Divider(height: 1, color: kLine),
                  SizedBox(height: 300, child: _lower()),
                ]),
              ),
            ])
          : ListView(padding: EdgeInsets.fromLTRB(16, 8, 16, 24), children: [
              Panel(child: Theme(
                data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                child: ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  initiallyExpanded: true,
                  title: Text('The task and its tests', style: TextStyle(fontWeight: FontWeight.w800, color: kInk)),
                  children: [_sideContent()],
                ),
              )),
              SizedBox(height: 12),
              SizedBox(height: 340, child: _editor(expand: true)),
              SizedBox(height: 10),
              Row(children: [Expanded(child: actions[0]), SizedBox(width: 8), Expanded(child: actions[2])]),
              SizedBox(height: 12),
              SizedBox(height: 380, child: Panel(child: _lower())),
            ]),
    );
  }

  Widget _tag(String t) => Container(
        padding: EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(color: kWarnSoft, borderRadius: BorderRadius.circular(999), border: Border.all(color: kWarnBorder)),
        child: Text(t, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: kWarnText)),
      );

  Widget _side() => ListView(padding: EdgeInsets.all(16), children: [_sideContent()]);

  Widget _sideContent() {
    final t = _task!;
    final pub = (_panel['public_tests'] as List? ?? []).cast<Map>();
    final ran = {for (final r in (_run?['tests'] as List? ?? []).cast<Map>()) r['name']: r};
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (MediaQuery.sizeOf(context).width >= 1000) ...[
        Text(_largeScreen, style: TextStyle(fontSize: 12, color: kMuted, fontStyle: FontStyle.italic)),
        SizedBox(height: 10),
      ],
      Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Expanded(child: Text('Task description', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: kInk))),
        MascotPlaceholder(size: 40, pose: 'point'),
      ]),
      SizedBox(height: 6),
      Text('${t['brief'] ?? ''}', style: TextStyle(color: kBody, height: 1.45)),
      if (t['months'] != null) ...[
        SizedBox(height: 6),
        Text('The plan runs every month for ${t['months']} months.', style: TextStyle(fontSize: 12, color: kMuted)),
      ],
      SizedBox(height: 16),
      Text('Public tests', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: kInk)),
      Text('Run them as often as you like. Nothing is scored until you submit.', style: TextStyle(fontSize: 12, color: kMuted)),
      SizedBox(height: 8),
      for (final (i, p) in pub.indexed)
        Container(
          margin: EdgeInsets.only(bottom: 8),
          padding: EdgeInsets.all(10),
          decoration: BoxDecoration(color: kSurface, borderRadius: BorderRadius.circular(12), border: Border.all(color: _tone(ran[p['name']]) ?? kLine)),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            _statusIcon(ran[p['name']]),
            SizedBox(width: 8),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Test ${i + 1}${p['kind'] == 'sample' ? ' · sample event' : ' · must pass'}',
                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: kPrimaryText)),
              Text('${p['name']}', style: TextStyle(color: kInk, height: 1.3)),
            ])),
          ]),
        ),
      Container(
        padding: EdgeInsets.all(10),
        decoration: BoxDecoration(color: kPrimarySoft, borderRadius: BorderRadius.circular(12)),
        child: Row(children: [
          Icon(Icons.lock_outline, size: 18, color: kPrimaryText),
          SizedBox(width: 8),
          Expanded(child: Text('${_panel['hidden_tests'] ?? 0} hidden events${_panel['futures'] != null ? ' and ${_panel['futures']} possible futures' : ''} are revealed only when you submit.',
              style: TextStyle(fontSize: 12, color: kPrimaryText))),
        ]),
      ),
      SizedBox(height: 16),
      Text('What you can write', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: kInk)),
      SizedBox(height: 6),
      _codeHint('if <condition>:   elif <condition>:   else:'),
      _codeHint('compare with < or >, combine with and / or / not'),
      _codeHint('maths: + - * /  min(a, b)  max(a, b)'),
      if (_panel['own_variables'] != null) _codeHint('${_panel['own_variables']}'),
      SizedBox(height: 8),
      Text('Actions', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
      for (final a in (_panel['actions'] as List? ?? []).cast<Map>()) _vocab('${a['code']}', '${a['meaning']}'),
      if ((_panel['assets'] as List? ?? []).isNotEmpty) _vocab('assets', (_panel['assets'] as List).join(', ')),
      SizedBox(height: 8),
      Text('Values', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
      for (final v in (_panel['values'] as List? ?? []).cast<Map>()) _vocab('${v['name']}', '${v['meaning']}'),
    ]);
  }

  Widget _codeHint(String t) => Padding(
        padding: EdgeInsets.only(bottom: 4),
        child: Text(t, style: GoogleFonts.robotoMono(fontSize: 12, color: kBody)),
      );

  Widget _vocab(String code, String meaning) => Padding(
        padding: EdgeInsets.only(top: 4),
        child: Text.rich(TextSpan(children: [
          TextSpan(text: code, style: GoogleFonts.robotoMono(fontSize: 12, fontWeight: FontWeight.w600, color: kPrimaryText)),
          TextSpan(text: '  $meaning', style: TextStyle(fontSize: 12, color: kMuted)),
        ])),
      );

  Color? _tone(Map? r) => r == null ? null : r['kind'] == 'sample' ? kWarnBorder : r['passed'] == true ? kGreen : kRed;

  Widget _statusIcon(Map? r) {
    if (r == null) return Icon(Icons.radio_button_unchecked, size: 20, color: kFaint);
    if (r['kind'] == 'sample') return Icon(Icons.insights, size: 20, color: kWarnIcon);
    return r['passed'] == true ? Icon(Icons.check_circle, size: 20, color: kGreen) : Icon(Icons.cancel, size: 20, color: kRed);
  }

  Widget _editor({bool expand = false}) => Container(
        decoration: BoxDecoration(color: appDark ? Color(0xFF14171F) : Color(0xFFF7F8F5), borderRadius: BorderRadius.circular(12), border: Border.all(color: kBorder)),
        padding: EdgeInsets.fromLTRB(12, 8, 12, 8),
        child: Semantics(
          label: 'Code editor',
          textField: true,
          child: Focus(
            onKeyEvent: (node, e) {
              if (e is KeyDownEvent && e.logicalKey == LogicalKeyboardKey.tab) {
                final sel = _code.selection;
                final t = _code.text;
                final start = sel.start < 0 ? t.length : sel.start;
                _code.value = TextEditingValue(text: t.replaceRange(start, sel.end < 0 ? t.length : sel.end, '    '), selection: TextSelection.collapsed(offset: start + 4));
                return KeyEventResult.handled;
              }
              return KeyEventResult.ignored;
            },
            child: TextField(
              controller: _code,
              maxLines: null,
              expands: expand,
              keyboardType: TextInputType.multiline,
              autocorrect: false,
              enableSuggestions: false,
              inputFormatters: [_AutoIndent()],
              style: GoogleFonts.robotoMono(fontSize: 14, height: 1.5, color: kInk),
              decoration: InputDecoration(border: InputBorder.none, isCollapsed: true, hintText: '# write your plan here'),
            ),
          ),
        ),
      );

  /// Below the code: the blocks you can use (like Scratch) and the test results, on one bar.
  Widget _lower() => Column(children: [
        TabBar(
          controller: _tabs,
          isScrollable: true,
          tabAlignment: TabAlignment.start,
          tabs: [Tab(icon: Icon(Icons.extension_rounded, size: 18), text: 'Blocks'), Tab(icon: Icon(Icons.fact_check_outlined, size: 18), text: 'Test results')],
        ),
        Expanded(child: TabBarView(controller: _tabs, children: [_blocks(), _results()])),
      ]);

  static const _cControl = Color(0xFFFFAB19), _cCond = Color(0xFF59C059), _cMath = Color(0xFF0FBD8C),
      _cValue = Color(0xFF4C97FF), _cAction = Color(0xFF9966FF), _cMine = Color(0xFFFF8C1A);

  Widget _blocks() {
    final values = [for (final v in (_panel['values'] as List? ?? []).cast<Map>()) '${v['name']}'];
    final meaning = {for (final v in (_panel['values'] as List? ?? []).cast<Map>()) '${v['name']}': '${v['meaning']}'};
    final assets = [for (final a in (_panel['assets'] as List? ?? [])) '$a'];
    final asset = assets.isEmpty ? 'fund' : assets.first;
    final actions = <(String, String, String)>[
      for (final a in (_panel['actions'] as List? ?? []).cast<Map>())
        ('${a['code']}'.split('(').first, '${a['code']}'.replaceAll('amount', 'cash').replaceAll('asset', asset), '${a['meaning']}'),
    ];
    Widget section(String title, Color c, List<Widget> chips) => Padding(
          padding: EdgeInsets.only(bottom: 10),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Container(width: 10, height: 10, decoration: BoxDecoration(color: c, shape: BoxShape.circle)),
              SizedBox(width: 6),
              Text(title, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: kMuted)),
            ]),
            SizedBox(height: 6),
            Wrap(spacing: 6, runSpacing: 6, children: chips),
          ]),
        );
    return ListView(padding: EdgeInsets.fromLTRB(12, 10, 12, 10), children: [
      Text('Tap a block to add it where the cursor is.', style: TextStyle(fontSize: 12, color: kMuted)),
      SizedBox(height: 8),
      section('Control', _cControl, [
        _block('if … :', _cControl, 'if ___:', 'Do the lines under it only when the condition is true. Fill the gap with a value, < or > and a number.', line: true),
        _block('elif … :', _cControl, 'elif ___:', 'Otherwise, if another condition is true', line: true),
        _block('else:', _cControl, 'else:', 'Otherwise', line: true),
      ]),
      section('Actions', _cAction, [for (final a in actions) _block(a.$1, _cAction, a.$2, a.$3, line: true)]),
      section('Conditions', _cCond, [
        _block('<', _cCond, ' < ', 'is less than'),
        _block('>', _cCond, ' > ', 'is more than'),
        _block('and', _cCond, ' and ', 'both must be true'),
        _block('or', _cCond, ' or ', 'one is enough'),
        _block('not', _cCond, 'not ', 'the opposite'),
      ]),
      section('Values', _cValue, [for (final v in values) _block(v, _cValue, v, meaning[v] ?? v)]),
      section('Maths', _cMath, [
        _block('+', _cMath, ' + ', 'plus'),
        _block('-', _cMath, ' - ', 'minus'),
        _block('*', _cMath, ' * ', 'times'),
        _block('/', _cMath, ' / ', 'divided by'),
        _block('min(a, b)', _cMath, 'min(cash, 1000)', 'the smaller of two'),
        _block('max(a, b)', _cMath, 'max(cash, 0)', 'the bigger of two'),
        _block('number', _cMath, '1000', 'a number'),
      ]),
      if (_panel['own_variables'] != null)
        section('My variables', _cMine, [
          _block('my_total = 0', _cMine, 'my_total = 0', 'make or set your own number', line: true),
          _block('my_total += cash', _cMine, 'my_total += cash', 'add to your own number', line: true),
        ]),
    ]);
  }

  Widget _block(String label, Color c, String code, String tip, {bool line = false}) => Tooltip(
        message: tip,
        child: Material(
          color: c,
          borderRadius: BorderRadius.circular(8),
          child: InkWell(
            borderRadius: BorderRadius.circular(8),
            onTap: () => _insert(code, line: line),
            child: Container(
              padding: EdgeInsets.symmetric(horizontal: 10, vertical: 7),
              decoration: BoxDecoration(borderRadius: BorderRadius.circular(8), border: Border.all(color: Colors.black.withValues(alpha: .15))),
              child: Text(label, style: GoogleFonts.robotoMono(fontSize: 13, fontWeight: FontWeight.w700, color: Colors.white)),
            ),
          ),
        ),
      );

  /// Insert a block's code. Statements go on a new line with the right indent; parts of an
  /// expression go where the cursor is.
  static const _gap = '___';

  /// Insert a block. Statements go on their own line with the right indent (`elif` and `else` line up
  /// with their `if`; anything after a line ending in ':' goes inside it). `if` and `elif` leave a gap
  /// (___) selected; values, comparisons and maths fill the selected gap, or go where the cursor is
  /// inside a condition or an action's brackets. Elsewhere they are refused with a hint.
  void _insert(String code, {bool line = false}) {
    final t = _code.text;
    final sel = _code.selection;
    final at = sel.isValid ? sel.end : t.length;
    final lineStart = t.lastIndexOf('\n', at > 0 ? at - 1 : 0) + 1;
    var lineEnd = t.indexOf('\n', at);
    if (lineEnd < 0) lineEnd = t.length;
    final current = t.substring(lineStart, lineEnd);

    if (!line) {
      if (sel.isValid && !sel.isCollapsed) {
        _set(t.replaceRange(sel.start, sel.end, code.trim()), sel.start + code.trim().length);
        return;
      }
      final before = t.substring(lineStart, at), after = t.substring(at, lineEnd);
      final trimmed = current.trimLeft();
      final inCondition = (trimmed.startsWith('if ') || trimmed.startsWith('elif ')) && after.contains(':');
      final inBrackets = '('.allMatches(before).length > ')'.allMatches(before).length;
      if (!inCondition && !inBrackets) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text('Tap "if" first, then fill its gap (___), or put the cursor inside a condition or the brackets of an action.')));
        return;
      }
      final glue = before.isNotEmpty && RegExp(r'[A-Za-z0-9_)]$').hasMatch(before) && !code.startsWith(' ') ? ' ' : '';
      final piece = glue + code;
      _set(t.replaceRange(at, at, piece), at + piece.length);
      return;
    }

    int indentOf(String l) => l.length - l.trimLeft().length;
    var indent = indentOf(current);
    final head = code.trimLeft();
    if (head.startsWith('elif') || head.startsWith('else')) {
      // Line up with the `if` this belongs to: the nearest if/elif above with a smaller indent
      // (or the same indent when the cursor is on that if line itself).
      final lines = t.substring(0, lineEnd).split('\n');
      for (var k = lines.length - 1; k >= 0; k--) {
        final l = lines[k], tl = l.trimLeft();
        if ((tl.startsWith('if ') || tl.startsWith('elif ')) && (indentOf(l) < indent || k == lines.length - 1)) {
          indent = indentOf(l);
          break;
        }
      }
    } else if (current.trimRight().endsWith(':')) {
      indent += 4; // inside the block
    }
    var block = ' ' * indent + code;
    if (head.endsWith(':') && !head.contains(_gap)) block += '\n' + ' ' * (indent + 4); // else: start its body
    final String text;
    final int insertAt;
    if (current.trim().isEmpty) {
      text = t.replaceRange(lineStart, lineEnd, block);
      insertAt = lineStart;
    } else {
      text = t.replaceRange(lineEnd, lineEnd, '\n$block');
      insertAt = lineEnd + 1;
    }
    final g = block.indexOf(_gap);
    if (g >= 0) {
      _code.value = TextEditingValue(text: text, selection: TextSelection(baseOffset: insertAt + g, extentOffset: insertAt + g + _gap.length));
    } else {
      _set(text, insertAt + block.length);
    }
  }

  void _set(String text, int cursor) => _code.value = TextEditingValue(text: text, selection: TextSelection.collapsed(offset: cursor));

  Widget _results({bool scroll = true}) {
    final children = <Widget>[
      Row(children: [
        Text('Test results', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: kInk)),
        SizedBox(width: 8),
        if (_busy) SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
        Spacer(),
        if (_result != null) TextButton.icon(onPressed: () => _showResult(_result!), icon: Icon(Icons.emoji_events_outlined), label: Text('Last result')),
      ]),
      SizedBox(height: 8),
      if (_error != null)
        Panel(color: kRedSoft, border: kRed, child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(Icons.error_outline, color: kRed),
          SizedBox(width: 8),
          Expanded(child: Text(_error!, style: GoogleFonts.robotoMono(fontSize: 13, color: kInk))),
        ]))
      else if (_run == null)
        Text('Press "Run tests" to check your plan against the public tests.', style: TextStyle(color: kMuted))
      else ...[
        Text(_run!['required_passed'] == true ? 'All required public tests pass. Submit to face the hidden events.' : 'Some required tests fail. Fix the plan and run again.',
            style: TextStyle(fontWeight: FontWeight.w700, color: _run!['required_passed'] == true ? kGreen : kRed)),
        SizedBox(height: 6),
        for (final r in (_run!['tests'] as List).cast<Map>())
          Padding(
            padding: EdgeInsets.only(bottom: 6),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              _statusIcon(r),
              SizedBox(width: 8),
              Expanded(child: Text(
                r['kind'] == 'sample'
                    ? '${r['name']}: your plan kept ${((r['metric'] as num) * 100).round()}% of what was possible.'
                    : '${r['name']}: ${r['passed'] == true ? 'passed' : 'failed${r['failed_variant'] != null ? ' (${_variant(r['failed_variant'])})' : ''}'}',
                style: TextStyle(color: kBody, height: 1.35),
              )),
            ]),
          ),
        Text('Ran in ${_run!['duration_ms']} ms. Hidden events: ${_run!['hidden_tests']}.', style: TextStyle(fontSize: 12, color: kMuted)),
      ],
    ];
    return scroll
        ? ListView(padding: EdgeInsets.fromLTRB(16, 12, 16, 12), children: children)
        : Column(crossAxisAlignment: CrossAxisAlignment.start, children: children);
  }

  String _variant(dynamic v) => v is Map ? v.entries.map((e) => '${e.key.toString().replaceAll('_', ' ')} ${e.value}').join(', ') : '$v';

  Future<void> _confirmSubmit() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (d) => AlertDialog(
        title: Text('Submit your plan?'),
        content: Text('Your plan will face every test, including the ${_panel['hidden_tests'] ?? 0} hidden events${_panel['futures'] != null ? ' and ${_panel['futures']} possible futures' : ''}. You can still improve it and submit again.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(d, false), child: Text('Keep editing')),
          FilledButton(style: FilledButton.styleFrom(minimumSize: Size(120, 44)), onPressed: () => Navigator.pop(d, true), child: Text('Submit')),
        ],
      ),
    );
    if (ok == true) _submit();
  }

  void _showResult(Map<String, dynamic> r) {
    final res = Map<String, dynamic>.from((r['reveal'] as Map?)?['result'] as Map? ?? {});
    final ok = r['accepted'] == true;
    final futures = res['futures'] as Map?;
    showDialog(
      context: context,
      builder: (d) => AlertDialog(
        title: Text(ok ? 'Plan accepted' : 'Not accepted yet', textAlign: TextAlign.center),
        content: SizedBox(
          width: 520,
          child: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Center(child: MascotPlaceholder(size: 150, pose: ok ? 'cheer' : 'think')),
            SizedBox(height: 8),
            if (ok)
              Center(child: Text('${r['points']} / 100 points${r['growth_index'] != null ? ' · growth ${r['growth_index']}' : ''}',
                  style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: kPrimaryText))),
            SizedBox(height: 12),
            Text('Required tests', style: TextStyle(fontWeight: FontWeight.w800, color: kInk)),
            for (final t in (res['obligatory'] as List? ?? []).cast<Map>())
              _line(t['passed'] == true ? Icons.check_circle : Icons.cancel, t['passed'] == true ? kGreen : kRed, '${t['name']}'),
            if ((res['optional'] as List? ?? []).isNotEmpty) ...[
              SizedBox(height: 10),
              Text('All events, hidden ones included', style: TextStyle(fontWeight: FontWeight.w800, color: kInk)),
              for (final t in (res['optional'] as List).cast<Map>())
                _line(Icons.insights, kWarnIcon, '${t['name']}: ${(((t['metric'] as num?) ?? 0) * 100).round()}% kept (chance ${(((t['probability'] as num?) ?? 0) * 100).round()}%)'),
            ] else if (!ok)
              Padding(padding: EdgeInsets.only(top: 10), child: Text('The hidden events open once every required test passes.', style: TextStyle(color: kMuted))),
            if (futures != null) ...[
              SizedBox(height: 10),
              Text('Possible futures', style: TextStyle(fontWeight: FontWeight.w800, color: kInk)),
              Text(futures.entries.where((e) => e.value is num).map((e) => '${e.key.toString().replaceAll('_', ' ')}: ${(e.value as num).round()}').join(' · '),
                  style: TextStyle(color: kBody)),
            ],
          ])),
        ),
        actions: [
          TextButton(onPressed: () { Navigator.pop(d); context.pop(); }, child: Text('Back to the mission')),
          FilledButton(style: FilledButton.styleFrom(minimumSize: Size(120, 44)), onPressed: () => Navigator.pop(d), child: Text('Keep improving')),
        ],
      ),
    );
  }

  Widget _line(IconData i, Color c, String t) => Padding(
        padding: EdgeInsets.only(top: 4),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(i, size: 18, color: c),
          SizedBox(width: 6),
          Expanded(child: Text(t, style: TextStyle(color: kBody))),
        ]),
      );
}

/// Pressing Enter keeps the line's indent, and adds 4 spaces after a line ending in ':'.
class _AutoIndent extends TextInputFormatter {
  @override
  TextEditingValue formatEditUpdate(TextEditingValue old, TextEditingValue now) {
    if (now.text.length != old.text.length + 1 || now.selection.baseOffset <= 0) return now;
    final at = now.selection.baseOffset;
    if (now.text[at - 1] != '\n') return now;
    final before = now.text.substring(0, at - 1);
    final line = before.substring(before.lastIndexOf('\n') + 1);
    var indent = line.length - line.trimLeft().length;
    if (line.trimRight().endsWith(':')) indent += 4;
    if (indent == 0) return now;
    final pad = ' ' * indent;
    return TextEditingValue(text: now.text.replaceRange(at, at, pad), selection: TextSelection.collapsed(offset: at + indent));
  }
}
