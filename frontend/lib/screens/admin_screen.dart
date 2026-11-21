// Admin panel: read-only monitoring of the backend (docs/tutor_agent.md,
// section 6). Tabs: Overview, Tutor calls (the masked prompts users write and
// the tutor's answers), Recommender, Event log. Users appear as pseudonymous
// ids only. The admin key is typed here, kept in memory, and sent as the
// X-Admin-Key header.

import 'dart:convert';
import 'package:flutter/material.dart';
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
      api.admin('summary', _key!),
      api.admin('llm-events?limit=100${_flaggedOnly ? '&flagged=true' : ''}', _key!),
      api.admin('reco-events?limit=100', _key!),
      api.admin('events?limit=100${_eventName != null ? '&name=${Uri.encodeQueryComponent(_eventName!)}' : ''}', _key!),
    ]);
  }

  void _refresh() => setState(() => _data = _load());

  @override
  void initState() {
    super.initState();
    if (_key != null) _data = _load();
  }

  @override
  Widget build(BuildContext context) {
    if (_key == null) return _keyGate();
    return DefaultTabController(
      length: 4,
      child: Scaffold(
        appBar: AppBar(
          title: Text('Admin panel'),
          actions: [
            IconButton(tooltip: 'Refresh', icon: Icon(Icons.refresh), onPressed: _refresh),
            IconButton(tooltip: 'Forget key', icon: Icon(Icons.logout), onPressed: () => setState(() { _key = null; _data = null; })),
          ],
          bottom: TabBar(isScrollable: true, tabs: [Tab(text: 'Overview'), Tab(text: 'Tutor calls'), Tab(text: 'Recommender'), Tab(text: 'Event log')]),
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
            final [summary, llm, reco, events] = snap.data!;
            return TabBarView(children: [
              _overview(summary),
              _llm((llm['items'] as List).cast<Map<String, dynamic>>()),
              _reco((reco['items'] as List).cast<Map<String, dynamic>>()),
              _events(events),
            ]);
          },
        ),
      ),
    );
  }

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
