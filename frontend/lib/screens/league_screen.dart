// Leagues: one per level (Beginner, Intermediate, Expert). You compete in your
// level's league; the others can be viewed. Swipe sideways through pages of 10
// learners. Real learners from GET /leagues, ranked by the Scales the server
// recorded for them (app/scales.py).

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../widgets/common.dart';

class LeagueScreen extends StatefulWidget {
  LeagueScreen({super.key});
  @override
  State<LeagueScreen> createState() => _LeagueScreenState();
}

class _LeagueScreenState extends State<LeagueScreen> {
  static const perPage = 10;
  PageController _pages = PageController();
  int _page = 0;
  String? _viewing; // league shown; null = your own

  Map<String, dynamic>? _data; // GET /leagues
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final s = context.read<AppState>();
    try {
      final d = await s.api.leagues(s.profile.name);
      s.syncScales(((d['me'] as Map?)?['scales'] as num?)?.toInt());
      if (mounted) setState(() { _data = d; _error = null; });
    } catch (_) {
      if (mounted) setState(() => _error = "Can't load the league right now.");
    }
  }

  List<(String, int, bool)> _rows(String level) {
    final lv = (_data?['levels'] as List? ?? []).cast<Map>().firstWhere((l) => l['name'] == level, orElse: () => {});
    return [for (final e in (lv['entries'] as List? ?? []).cast<Map>()) (e['display_name'] as String, (e['scales'] as num).toInt(), e['is_me'] == true)];
  }

  @override
  void dispose() {
    _pages.dispose();
    super.dispose();
  }

  void _go(int p) => _pages.animateToPage(p, duration: Duration(milliseconds: 350), curve: Curves.easeOutCubic);

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final mine = s.level.name;
    final viewing = _viewing ?? mine;
    final own = viewing == mine;
    final rows = _rows(viewing);
    final myRank = rows.indexWhere((r) => r.$3);
    final pageCount = (rows.length / perPage).ceil().clamp(1, 999);
    return Scaffold(
      appBar: StatsBar(title: '$viewing league', subtitle: own ? 'Your league' : null),
      body: PageWidth(max: 1000, child: Column(children: [
        Padding(
          padding: EdgeInsets.fromLTRB(20, 12, 20, 12),
          child: SegmentedButton<String>(
            showSelectedIcon: false,
            segments: [
              for (final l in levels)
                ButtonSegment(value: l.name, icon: l.name == mine ? Icon(Icons.person, size: 16) : null, label: Text(l.name, overflow: TextOverflow.ellipsis)),
            ],
            selected: {viewing},
            onSelectionChanged: (v) => setState(() {
              _viewing = v.first;
              _page = 0;
              _pages.dispose();
              _pages = PageController();
            }),
          ),
        ),
        if (_data == null && _error == null) Expanded(child: Center(child: CircularProgressIndicator())),
        if (_error != null) Expanded(child: Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
          Text(_error!, style: TextStyle(color: kMuted)),
          TextButton(onPressed: () { setState(() => _error = null); _load(); }, child: Text('Try again')),
        ]))),
        if (_data != null) ...[
        if (own && myRank >= 0)
        Padding(
          padding: EdgeInsets.fromLTRB(20, 0, 20, 8),
          child: Panel(
            color: kPrimarySoft,
            border: kPrimarySoft,
            child: Row(children: [
              ScaleIcon(size: 26),
              SizedBox(width: 10),
              Expanded(
                child: Text('You are #${myRank + 1} of ${rows.length} in the $mine league, with ${s.xp} Scales',
                    style: TextStyle(fontWeight: FontWeight.w700, color: kPrimaryText)),
              ),
              TextButton(onPressed: () => _go(myRank ~/ perPage), child: Text('Find me')),
            ]),
          ),
        ),
        Expanded(
          child: PageView.builder(
            key: ValueKey(viewing),
            controller: _pages,
            itemCount: pageCount,
            onPageChanged: (p) => setState(() => _page = p),
            itemBuilder: (context, p) {
              final start = p * perPage;
              final slice = rows.isEmpty ? <(String, int, bool)>[] : rows.sublist(start, (start + perPage).clamp(0, rows.length));
              return ListView(padding: EdgeInsets.symmetric(horizontal: 20), children: [
                if (rows.isEmpty)
                  Padding(padding: EdgeInsets.all(24), child: Center(child: Text('No learners in this league yet.', style: TextStyle(color: kMuted)))),
                for (final (i, r) in slice.indexed) _Row(rank: start + i + 1, name: r.$3 ? '${r.$1} (you)' : r.$1, scales: r.$2, me: r.$3),
              ]);
            },
          ),
        ),
        Padding(
          padding: EdgeInsets.fromLTRB(12, 4, 12, 12),
          child: Row(children: [
            IconButton(tooltip: 'Previous page', onPressed: _page > 0 ? () => _go(_page - 1) : null, icon: Icon(Icons.chevron_left)),
            Expanded(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                  for (var i = 0; i < pageCount; i++)
                    AnimatedContainer(
                      duration: Duration(milliseconds: 250),
                      margin: EdgeInsets.symmetric(horizontal: 3),
                      width: i == _page ? 20 : 8,
                      height: 8,
                      decoration: BoxDecoration(color: i == _page ? kPrimary : kBorder, borderRadius: BorderRadius.circular(4)),
                    ),
                ]),
                SizedBox(height: 4),
                Text('$viewing league · ranks ${rows.isEmpty ? 0 : _page * perPage + 1}-${((_page + 1) * perPage).clamp(0, rows.length)} of ${rows.length}',
                    style: TextStyle(fontSize: 11, color: kMuted)),
              ]),
            ),
            IconButton(tooltip: 'Next page', onPressed: _page < pageCount - 1 ? () => _go(_page + 1) : null, icon: Icon(Icons.chevron_right)),
          ]),
        ),
        ],
      ])),
    );
  }
}

class _Row extends StatelessWidget {
  final int rank;
  final String name;
  final int scales;
  final bool me;
  _Row({required this.rank, required this.name, required this.scales, required this.me});

  @override
  Widget build(BuildContext context) {
    final medal = {1: Color(0xFFE0A100), 2: Color(0xFF9AA4AE), 3: Color(0xFFB8733C)}[rank];
    return Container(
      margin: EdgeInsets.only(bottom: 8),
      padding: EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: me ? kPrimarySoft : kSurface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: me ? kPrimary : kLine, width: me ? 2 : 1),
      ),
      child: Row(children: [
        SizedBox(
          width: 34,
          child: medal != null
              ? CircleAvatar(radius: 13, backgroundColor: medal, child: Text('$rank', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: Colors.white)))
              : Text('$rank', style: TextStyle(fontWeight: FontWeight.w700, color: kMuted)),
        ),
        Expanded(child: Text(name, style: TextStyle(fontWeight: me ? FontWeight.w800 : FontWeight.w500, color: kInk))),
        ScaleIcon(size: 16),
        SizedBox(width: 4),
        Text('$scales', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
      ]),
    );
  }
}
