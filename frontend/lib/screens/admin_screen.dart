// Admin panel: monitoring of the backend (docs/tutor_agent.md section 6,
// docs/admin_and_profile.md). Tabs: Overview, Alerts, Questions (item quality),
// Confidence (how sure vs how right), Advice watch, Feedback (reports, with a
// status you can change), Insights (aggregate clients, clicks, A/B), Study,
// Tutor calls (the masked prompts users write and the tutor's answers),
// Recommender, Event log. Users appear as pseudonymous
// ids only. The admin key is typed here, kept in memory, and sent as the
// X-Admin-Key header.

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../widgets/common.dart';

class AdminScreen extends StatefulWidget {
  AdminScreen({super.key});
  @override
  State<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends State<AdminScreen> {
  static String? _key; // memory only, cleared when the app reloads
  final _keyField = TextEditingController();
  Future<List<Map<String, dynamic>>>? _data;
  bool _flaggedOnly = false;
  String? _eventName;

  Future<List<Map<String, dynamic>>> _load() {
    final api = context.read<AppState>().api;
    return Future.wait([
      api.admin('summary', _key),
      api.admin('llm-events?limit=100${_flaggedOnly ? '&flagged=true' : ''}', _key),
      api.admin('reco-events?limit=100', _key),
      api.admin('events?limit=100${_eventName != null ? '&name=${Uri.encodeQueryComponent(_eventName!)}' : ''}', _key),
      api.admin('overview', _key),
      api.admin('items', _key),
      api.admin('calibration', _key),
      api.admin('advice-watch', _key),
      api.admin('feedback', _key),
      api.admin('client-insights', _key),
      api.admin('node-opened', _key),
      api.admin('ab-results', _key),
      api.admin('study', _key),
    ]);
  }

  void _refresh() => setState(() => _data = _load());

  @override
  void initState() {
    super.initState();
    if (context.read<AppState>().isAdmin) _data = _load();
  }

  @override
  Widget build(BuildContext context) {
    // Admin accounts only: anyone else gets a polite stop (the backend refuses them too).
    if (!context.watch<AppState>().isAdmin) return _adminsOnly();
    return DefaultTabController(
      length: 11,
      child: Scaffold(
        appBar: AppBar(
          title: Text('Admin panel'),
          actions: [
            IconButton(tooltip: 'Refresh', icon: Icon(Icons.refresh), onPressed: _refresh),
            IconButton(tooltip: 'Forget key', icon: Icon(Icons.logout), onPressed: () => setState(() { _key = null; _data = null; })),
          ],
          bottom: TabBar(isScrollable: true, tabs: [Tab(text: 'Overview'), Tab(text: 'Alerts'), Tab(text: 'Questions'), Tab(text: 'Confidence'), Tab(text: 'Advice watch'),
              Tab(text: 'Feedback'), Tab(text: 'Insights'), Tab(text: 'Study'), Tab(text: 'Tutor calls'), Tab(text: 'Recommender'), Tab(text: 'Event log')]),
        ),
        body: FutureBuilder<List<Map<String, dynamic>>>(
          future: _data,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) return Center(child: CircularProgressIndicator());
            if (snap.hasError) {
              return ListView(padding: EdgeInsets.all(20), children: [
                Panel(color: kRedSoft, border: kRed, child: Text('${snap.error}', style: TextStyle(color: kInk))),
                SizedBox(height: 12),
                FilledButton(onPressed: _refresh, child: Text('Try again')),
              ]);
            }
            final [summary, llm, reco, events, overview, items, calibration, advice, feedback, insights, clicks, ab, study] = snap.data!;
            return TabBarView(children: [
              _overview(summary),
              _alerts(overview),
              _items(items),
              _calibration(calibration),
              _advice(advice),
              _feedback(feedback),
              _insights(insights, clicks, ab),
              _study(study),
              _llm((llm['items'] as List).cast<Map<String, dynamic>>()),
              _reco((reco['items'] as List).cast<Map<String, dynamic>>()),
              _events(events),
            ]);
          },
        ),
      ),
    );
  }

  Widget _adminsOnly() => Scaffold(
        appBar: AppBar(title: Text('Admin panel')),
        body: ListView(padding: EdgeInsets.all(24), children: [
          Center(child: MascotPlaceholder(size: 200, pose: 'think')),
          SizedBox(height: 12),
          Center(child: Text('This page is for admins only', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: kInk))),
          SizedBox(height: 6),
          Center(child: Text('Sign in with an admin account to open it.', textAlign: TextAlign.center, style: TextStyle(color: kMuted))),
          SizedBox(height: 18),
          Center(child: FilledButton(style: FilledButton.styleFrom(minimumSize: Size(120, 44)), onPressed: () => GoRouter.of(context).go('/wheel'), child: Text('Back to the app'))),
        ]),
      );

  // ignore: unused_element
  Widget _keyGate() => Scaffold(
        appBar: AppBar(title: Text('Admin panel')),
        body: ListView(padding: EdgeInsets.all(20), children: [
          Text('Enter the admin key', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: kInk)),
          SizedBox(height: 6),
          Text('It is the backend ADMIN_KEY. It stays in memory on this device and is sent in a request header only.',
              style: TextStyle(color: kMuted)),
          SizedBox(height: 16),
          TextField(
            controller: _keyField,
            obscureText: true,
            decoration: InputDecoration(labelText: 'Admin key', border: OutlineInputBorder(borderRadius: BorderRadius.circular(12))),
            onSubmitted: (_) => _unlock(),
          ),
          SizedBox(height: 12),
          FilledButton(onPressed: _unlock, child: Text('Open the panel')),
        ]),
      );

  void _unlock() {
    if (_keyField.text.trim().isEmpty) return;
    setState(() {
      _key = _keyField.text.trim();
      _data = _load();
    });
  }

  Widget _stat(String label, Object? value, {Color? tone}) => Container(
        padding: EdgeInsets.all(14),
        decoration: BoxDecoration(color: kSurface, borderRadius: BorderRadius.circular(14), border: Border.all(color: tone ?? kLine)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('${value ?? 0}', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: tone ?? kInk)),
          SizedBox(height: 2),
          Text(label, style: TextStyle(fontSize: 12, color: kMuted)),
        ]),
      );

  Widget _overview(Map<String, dynamic> s) {
    final avg = s['llm_avg_latency_ms'];
    return ListView(padding: EdgeInsets.all(16), children: [
      GridView.count(
        crossAxisCount: 2,
        shrinkWrap: true,
        physics: NeverScrollableScrollPhysics(),
        mainAxisSpacing: 10,
        crossAxisSpacing: 10,
        childAspectRatio: 1.9,
        children: [
          _stat('Users', s['users']),
          _stat('Events (24 h)', s['events_24h']),
          _stat('Tutor calls (24 h)', s['llm_calls_24h']),
          _stat('Tutor calls total', s['llm_calls']),
          _stat('Flagged for review', s['llm_flagged'], tone: (s['llm_flagged'] ?? 0) > 0 ? kRed : null),
          _stat('Fell back to stored text', s['llm_fallbacks']),
          _stat('Avg tutor latency', avg == null ? '-' : '${(avg as num).round()} ms'),
          _stat('Recommender events', s['reco_events']),
        ],
      ),
      SizedBox(height: 12),
      Text('Users are shown as pseudonymous ids. Tutor text is stored with personal data masked.', style: TextStyle(fontSize: 12, color: kMuted)),
    ]);
  }

  Widget _empty(String text) => ListView(padding: EdgeInsets.all(24), children: [
        Icon(Icons.inbox_outlined, size: 40, color: kFaint),
        SizedBox(height: 8),
        Text(text, textAlign: TextAlign.center, style: TextStyle(color: kMuted)),
      ]);

  Widget _llm(List<Map<String, dynamic>> items) => Column(children: [
        SwitchListTile(
          title: Text('Flagged only'),
          value: _flaggedOnly,
          onChanged: (v) => setState(() {
            _flaggedOnly = v;
            _data = _load();
          }),
        ),
        Expanded(
          child: items.isEmpty
              ? _empty('No tutor calls yet. They appear here once the backend logs POST /tutor calls.')
              : ListView.builder(
                  padding: EdgeInsets.fromLTRB(16, 0, 16, 16),
                  itemCount: items.length,
                  itemBuilder: (_, i) {
                    final r = items[i];
                    final failed = (r['checks_failed'] as List).cast<String>();
                    final flagged = r['flagged'] == true;
                    return Padding(
                      padding: EdgeInsets.only(bottom: 10),
                      child: Panel(
                        border: flagged ? kRed : null,
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Wrap(spacing: 6, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
                            _chip(r['mode'] ?? 'call'),
                            if (r['intent'] != null) _chip(r['intent'], tone: (r['intent'] == 'advice_request' || r['intent'] == 'injection') ? kRed : null),
                            if (flagged) _chip('flagged', tone: kRed),
                            if (r['fallback_used'] == true) _chip('fallback', tone: kWarnText),
                            for (final f in failed) _chip('check: $f', tone: kRed),
                          ]),
                          SizedBox(height: 8),
                          Text('User asked', style: TextStyle(fontSize: 11, color: kMuted)),
                          Text(r['prompt'] ?? '(no text stored)', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
                          if (r['answer'] != null) ...[
                            SizedBox(height: 6),
                            Text('Tutor answered', style: TextStyle(fontSize: 11, color: kMuted)),
                            Text(r['answer'], style: TextStyle(color: kBody)),
                          ],
                          SizedBox(height: 8),
                          Text(
                            [
                              _when(r['ts']),
                              'user ${r['user'] ?? '-'}',
                              if (r['node'] != null) 'skill ${r['node']}',
                              if (r['model'] != null) r['model'],
                              if (r['latency_ms'] != null) '${r['latency_ms']} ms',
                              if (r['tokens_in'] != null) '${r['tokens_in']}+${r['tokens_out'] ?? 0} tokens',
                              if (r['prompt_version'] != null) r['prompt_version'],
                            ].join(' · '),
                            style: TextStyle(fontSize: 11, color: kMuted),
                          ),
                        ]),
                      ),
                    );
                  },
                ),
        ),
      ]);

  Widget _reco(List<Map<String, dynamic>> items) => items.isEmpty
      ? _empty('No recommender events yet. They appear once the backend logs onboarding paths and recommendations.')
      : ListView.separated(
          padding: EdgeInsets.all(16),
          itemCount: items.length,
          separatorBuilder: (_, __) => Divider(color: kLine),
          itemBuilder: (_, i) {
            final r = items[i];
            return ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text('${r['type']}${r['node'] != null ? ' · ${r['node']}' : ''}', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
              subtitle: Text(
                [
                  _when(r['ts']),
                  'user ${r['user'] ?? '-'}',
                  if (r['path'] != null) 'path ${(r['path'] as List).join(' > ')}',
                  if (r['predicted_m'] != null) 'predicted ${r['predicted_m']}',
                  if (r['observed'] != null) 'observed ${r['observed']}',
                  if (r['router_version'] != null) r['router_version'],
                ].join(' · '),
                style: TextStyle(fontSize: 12, color: kMuted),
              ),
            );
          },
        );

  Widget _events(Map<String, dynamic> data) {
    final items = (data['items'] as List).cast<Map<String, dynamic>>();
    final names = (data['names'] as List).cast<Map<String, dynamic>>();
    return Column(children: [
      SizedBox(
        height: 52,
        child: ListView(scrollDirection: Axis.horizontal, padding: EdgeInsets.fromLTRB(16, 8, 16, 4), children: [
          Padding(
            padding: EdgeInsets.only(right: 6),
            child: ChoiceChip(label: Text('All'), selected: _eventName == null, onSelected: (_) => setState(() { _eventName = null; _data = _load(); })),
          ),
          for (final n in names)
            Padding(
              padding: EdgeInsets.only(right: 6),
              child: ChoiceChip(
                label: Text('${n['name']} (${n['count']})'),
                selected: _eventName == n['name'],
                onSelected: (_) => setState(() { _eventName = n['name'] as String; _data = _load(); }),
              ),
            ),
        ]),
      ),
      Expanded(
        child: items.isEmpty
            ? _empty('No events yet.')
            : ListView.separated(
                padding: EdgeInsets.fromLTRB(16, 4, 16, 16),
                itemCount: items.length,
                separatorBuilder: (_, __) => Divider(color: kLine, height: 1),
                itemBuilder: (_, i) {
                  final e = items[i];
                  return ExpansionTile(
                    tilePadding: EdgeInsets.zero,
                    title: Text(e['name'] as String, style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
                    subtitle: Text('${_when(e['ts'])} · user ${e['user'] ?? '-'}${e['variant'] != null ? ' · variant ${e['variant']}' : ''}',
                        style: TextStyle(fontSize: 12, color: kMuted)),
                    children: [
                      Container(
                        width: double.infinity,
                        padding: EdgeInsets.all(10),
                        decoration: BoxDecoration(color: kBg, borderRadius: BorderRadius.circular(8), border: Border.all(color: kLine)),
                        child: SelectableText(const JsonEncoder.withIndent('  ').convert(e['payload']),
                            style: TextStyle(fontFamily: 'monospace', fontSize: 12, color: kBody)),
                      ),
                      SizedBox(height: 8),
                    ],
                  );
                },
              ),
      ),
    ]);
  }

  // ------------------------------------------------------------ insights views (Mateusz's admin API)

  String _pct(Object? v) => v == null ? '-' : '${((v as num) * 100).round()}%';
  String _num(Object? v, [int digits = 2]) => v == null ? '-' : (v is int ? '$v' : (v as num).toStringAsFixed(digits));

  Widget _grid(List<Widget> tiles) => LayoutBuilder(builder: (context, c) => GridView.count(
        crossAxisCount: c.maxWidth > 900 ? 4 : 2,
        shrinkWrap: true,
        physics: NeverScrollableScrollPhysics(),
        mainAxisSpacing: 10,
        crossAxisSpacing: 10,
        childAspectRatio: c.maxWidth > 900 ? 2.4 : 1.9,
        children: tiles,
      ));

  Widget _h(String text, [String? sub]) => Padding(
        padding: EdgeInsets.only(top: 18, bottom: 8),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(text, style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: kInk)),
          if (sub != null) Text(sub, style: TextStyle(fontSize: 12, color: kMuted)),
        ]),
      );

  /// A scrollable table: header row plus rows of cells.
  Widget _table(List<String> head, List<List<String>> rows) => rows.isEmpty
      ? Padding(padding: EdgeInsets.all(12), child: Text('No data yet.', style: TextStyle(color: kMuted)))
      : SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: DataTable(
            headingRowHeight: 38,
            dataRowMinHeight: 34,
            dataRowMaxHeight: 40,
            columnSpacing: 22,
            headingTextStyle: TextStyle(fontWeight: FontWeight.w700, color: kMuted, fontSize: 12),
            columns: [for (final h in head) DataColumn(label: Text(h))],
            rows: [for (final r in rows) DataRow(cells: [for (final c in r) DataCell(Text(c, style: TextStyle(color: kInk, fontSize: 13)))])],
          ),
        );

  /// Key-value view for nested aggregate data (client insights, study metrics).
  Widget _kv(Object? v, [int depth = 0]) {
    if (v is Map) {
      return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        for (final e in v.entries)
          if (e.value is Map || e.value is List)
            Padding(
              padding: EdgeInsets.only(left: depth * 14.0, top: 6),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('${e.key}'.replaceAll('_', ' '), style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
                _kv(e.value, depth + 1),
              ]),
            )
          else
            Padding(
              padding: EdgeInsets.only(left: depth * 14.0, top: 3),
              child: Text('${'${e.key}'.replaceAll('_', ' ')}: ${e.value ?? '-'}', style: TextStyle(color: kBody)),
            ),
      ]);
    }
    if (v is List) {
      if (v.isEmpty) return Padding(padding: EdgeInsets.only(left: depth * 14.0), child: Text('none', style: TextStyle(color: kMuted)));
      return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [for (final x in v.take(20)) _kv(x is Map || x is List ? x : {'·': x}, depth)]);
    }
    return Text('$v', style: TextStyle(color: kBody));
  }

  Widget _alerts(Map<String, dynamic> o) {
    final alerts = (o['alerts'] as List).cast<Map<String, dynamic>>();
    return ListView(padding: EdgeInsets.all(16), children: [
      _grid([
        _stat('Users', o['users']),
        _stat('Answers (24 h)', o['attempts_last_24h']),
        _stat('Finished the survey', o['onboarded']),
        _stat('Open reports', o['open_reports'], tone: (o['open_reports'] ?? 0) > 0 ? kWarnIcon : null),
        _stat('Tutor answers', o['tutor_answers']),
        _stat('Tutor fallback rate', _pct(o['tutor_fallback_rate'])),
      ]),
      _h('Alerts', 'Red first: tutor advice, then reports and questions to check.'),
      if (alerts.isEmpty) Text('No alerts.', style: TextStyle(color: kMuted)),
      for (final a in alerts)
        Container(
          margin: EdgeInsets.only(bottom: 8),
          padding: EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: kSurface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: a['level'] == 'red' ? kRed : kWarnBorder),
          ),
          child: Wrap(spacing: 8, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [
            _chip('${a['kind']}', tone: a['level'] == 'red' ? kRed : kWarnIcon),
            Text('${a['target_id'] ?? a['message'] ?? ''}', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
            for (final f in (a['flags'] as List? ?? [])) _chip('$f'.replaceAll('_', ' ')),
          ]),
        ),
    ]);
  }

  Widget _items(Map<String, dynamic> d) {
    final items = (d['items'] as List).cast<Map<String, dynamic>>();
    final hard = (d['hard'] as List).cast<Map<String, dynamic>>();
    return ListView(padding: EdgeInsets.all(16), children: [
      _h('Questions', 'From first attempts. Low success, a big confidence gap or low discrimination mean the question needs a look.'),
      _table(['Question', 'Skill', 'Level', 'Answers', 'Right', 'Sure (1-5)', 'Gap', 'Discrimination', 'Median time', 'Used a hint'], [
        for (final i in items)
          ['${i['task_id']}', '${i['node']}', '${i['level']}', '${i['n']}', _pct(i['success']), _num(i['mean_confidence'], 1),
            _num(i['calibration_gap']), _num(i['discrimination']), i['median_time_s'] == null ? '-' : '${_num(i['median_time_s'], 0)} s', _pct(i['hint_share'])],
      ]),
      _h('Hard tasks', 'Accepted programs, points and the first failing test.'),
      if (hard.isEmpty) Text('No hard-task attempts yet.', style: TextStyle(color: kMuted)) else _kv(hard),
    ]);
  }

  Widget _calibration(Map<String, dynamic> d) {
    final series = Map<String, dynamic>.from(d['series'] as Map);
    final all = (series['all'] as List? ?? []).cast<Map<String, dynamic>>();
    final groups = Map<String, dynamic>.from(series['groups'] as Map? ?? {});
    List<List<String>> rows(List<Map<String, dynamic>> r) =>
        [for (final w in r) ['${w['week']}', '${w['n']}', _num(w['mean_confidence']), _num(w['mean_score']), _num(w['gap']), _num(w['brier'], 3)]];
    const head = ['Week', 'Answers', 'How sure (0-1)', 'How right (0-1)', 'Gap', 'Brier'];
    return ListView(padding: EdgeInsets.all(16), children: [
      _h('How sure vs how right', 'A positive gap means learners are more confident than correct. Lower Brier is better.'),
      _table(head, rows(all)),
      for (final g in groups.entries) ...[
        _h('Age group: ${g.key}'),
        _table(head, rows((g.value as List).cast<Map<String, dynamic>>())),
      ],
      _h('Survey self-rating vs knowledge score'),
      _table(['Self-rating', 'Knowledge score'], [
        for (final r in (d['onboarding_self_rating'] as List).cast<Map<String, dynamic>>()) ['${r['self_rating'] ?? 'not given'}', '${r['knowledge_score']}'],
      ]),
    ]);
  }

  Widget _advice(Map<String, dynamic> d) {
    if ((d['n'] ?? 0) == 0) return _empty('No tutor answers yet.');
    final alert = Map<String, dynamic>.from(d['advice_alert'] as Map? ?? {});
    return ListView(padding: EdgeInsets.all(16), children: [
      Panel(
        color: alert['on'] == true ? kRedSoft : kGreenSoft,
        border: alert['on'] == true ? kRed : kGreen,
        child: Text(
          alert['on'] == true
              ? 'Advice alert ON: ${alert['failing']} of ${alert['last_hour']} answers in the last hour failed the no-advice checks.'
              : 'No advice alert: ${alert['failing'] ?? 0} of ${alert['last_hour'] ?? 0} answers in the last hour failed the checks.',
          style: TextStyle(fontWeight: FontWeight.w700, color: kInk),
        ),
      ),
      SizedBox(height: 12),
      _grid([
        _stat('Tutor answers', d['n']),
        _stat('Fallback rate', _pct(d['fallback_rate'])),
        _stat('Flagged for review', d['flagged'], tone: (d['flagged'] ?? 0) > 0 ? kRed : null),
        _stat('Latency p50', d['latency_ms_p50'] == null ? '-' : '${d['latency_ms_p50']} ms'),
        _stat('Latency p95', d['latency_ms_p95'] == null ? '-' : '${d['latency_ms_p95']} ms'),
      ]),
      _h('What people asked'),
      Wrap(spacing: 6, runSpacing: 6, children: [for (final e in (d['intents'] as Map? ?? {}).entries) _chip('${e.key}: ${e.value}', tone: e.key == 'advice_request' || e.key == 'injection' ? kRed : null)]),
      _h('Checks that failed'),
      (d['checks_failed'] as Map? ?? {}).isEmpty
          ? Text('None.', style: TextStyle(color: kMuted))
          : Wrap(spacing: 6, runSpacing: 6, children: [for (final e in (d['checks_failed'] as Map).entries) _chip('${e.key}: ${e.value}', tone: kRed)]),
      _h('Models'),
      Wrap(spacing: 6, runSpacing: 6, children: [for (final e in (d['models'] as Map? ?? {}).entries) _chip('${e.key}: ${e.value}')]),
    ]);
  }

  Future<void> _setStatus(int id, String status) async {
    try {
      await context.read<AppState>().api.adminWrite('PATCH', 'feedback/$id', {'status': status}, _key);
      _refresh();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Couldn't change the status: $e")));
    }
  }

  Widget _feedback(Map<String, dynamic> d) {
    final reports = (d['reports'] as List).cast<Map<String, dynamic>>();
    final alerts = (d['alerts'] as List).cast<Map<String, dynamic>>();
    return ListView(padding: EdgeInsets.all(16), children: [
      if (alerts.isNotEmpty) ...[
        _h('Alerts'),
        for (final a in alerts) Padding(padding: EdgeInsets.only(bottom: 6), child: _kv(a)),
      ],
      _h('Reports', '"Report a problem" and ratings from learners. Text is masked before it is stored.'),
      if (reports.isEmpty) Text('No reports yet.', style: TextStyle(color: kMuted)),
      for (final r in reports)
        Container(
          margin: EdgeInsets.only(bottom: 8),
          padding: EdgeInsets.all(12),
          decoration: BoxDecoration(color: kSurface, borderRadius: BorderRadius.circular(12), border: Border.all(color: kLine)),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Wrap(spacing: 8, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [
              _chip('${r['kind']}'.replaceAll('_', ' '), tone: r['kind'] == 'wrong_fact' || r['kind'] == 'bug' ? kRed : null),
              Text('${r['where']} · ${r['target_id']}', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
              if (r['rating'] != null) _chip('${r['rating']}/5'),
              Text('${r['ts']}'.split('.').first.replaceAll('T', ' '), style: TextStyle(fontSize: 12, color: kMuted)),
            ]),
            if (r['text'] != null) Padding(padding: EdgeInsets.only(top: 6), child: Text('${r['text']}', style: TextStyle(color: kBody))),
            SizedBox(height: 6),
            Row(children: [
              Text('Status: ', style: TextStyle(color: kMuted)),
              DropdownButton<String>(
                value: r['status'] as String,
                underline: SizedBox(),
                items: [for (final st in ['new', 'triaged', 'fixed', 'wont_fix']) DropdownMenuItem(value: st, child: Text(st.replaceAll('_', ' ')))],
                onChanged: (v) {
                  if (v != null && v != r['status']) _setStatus(r['id'] as int, v);
                },
              ),
            ]),
          ]),
        ),
    ]);
  }

  Widget _insights(Map<String, dynamic> ci, Map<String, dynamic> clicks, Map<String, dynamic> ab) {
    final rest = Map<String, dynamic>.from(ci)..remove('note')..remove('users');
    return ListView(padding: EdgeInsets.all(16), children: [
      _h('Client insights', '${ci['note'] ?? ''}'),
      _grid([_stat('Learners in the insights', ci['users'])]),
      if (rest.isEmpty)
        Padding(padding: EdgeInsets.only(top: 8), child: Text('Groups appear once each has at least 5 learners (privacy).', style: TextStyle(color: kMuted)))
      else
        Panel(child: _kv(rest)),
      _h('Where learners open missions', 'Self-chosen clicks feed the next-step model.'),
      _grid([
        _stat('Missions opened', clicks['total']),
        _stat('Self-chosen share', _pct(clicks['self_chosen_share'])),
      ]),
      SizedBox(height: 8),
      Wrap(spacing: 6, runSpacing: 6, children: [for (final e in (clicks['by_source'] as Map? ?? {}).entries) _chip('${e.key}'.replaceAll('_', ' ') + ': ${e.value}')]),
      _h('A/B variants'),
      _table(['Variant', 'Users', 'Quiz before', 'Quiz after', 'Confidence before', 'Confidence after', 'Chose "hold"'], [
        for (final e in ab.entries)
          if (e.value is Map)
            ['${e.key}', '${e.value['users']}', _num(e.value['benchmark_before_avg']), _num(e.value['benchmark_after_avg']),
              _num(e.value['confidence_before_avg']), _num(e.value['confidence_after_avg']), _pct(e.value['hold_share'])],
      ]),
    ]);
  }

  Widget _study(Map<String, dynamic> d) => ListView(padding: EdgeInsets.all(16), children: [
        _h('Hallway study', '${d['note'] ?? ''}'),
        _grid([_stat('Participants', d['participants'])]),
        SizedBox(height: 10),
        (d['metrics'] as Map? ?? {}).isEmpty
            ? Text('Results appear after participants finish the before and after checks.', style: TextStyle(color: kMuted))
            : Panel(child: _kv(d['metrics'])),
      ]);

  Widget _chip(String text, {Color? tone}) => Container(
        padding: EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          color: (tone ?? kPrimary).withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(999),
        ),
        child: Text(text, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: tone ?? kPrimaryText)),
      );

  String _when(Object? ts) {
    if (ts == null) return '-';
    final t = DateTime.tryParse(ts as String)?.toLocal();
    if (t == null) return ts;
    String two(int n) => n.toString().padLeft(2, '0');
    return '${t.year}-${two(t.month)}-${two(t.day)} ${two(t.hour)}:${two(t.minute)}';
  }
}
