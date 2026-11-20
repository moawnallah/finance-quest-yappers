// Weekly league: its own tab. Swipe sideways through pages of 10 learners,
// with page dots and arrows. Ranks Scales earned from learning only.
// The other learners are demo data until the backend serves real rankings.

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
  final _pages = PageController();
  int _page = 0;

  // 29 demo learners with fixed scores, plus you.
  static final _demo = [for (var i = 0; i < 29; i++) ('Learner ${i + 1}', 420 - i * 14 - (i % 3) * 3)];

  @override
  void dispose() {
    _pages.dispose();
    super.dispose();
  }

  void _go(int p) => _pages.animateToPage(p, duration: Duration(milliseconds: 350), curve: Curves.easeOutCubic);

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final rows = [..._demo, ('You', s.xp)]..sort((a, b) => b.$2.compareTo(a.$2));
    final myRank = rows.indexWhere((r) => r.$1 == 'You');
    final pageCount = (rows.length / perPage).ceil();
    return Scaffold(
      appBar: StatsBar(title: 'Weekly league', subtitle: 'Resets Monday'),
      body: Column(children: [
        Padding(
          padding: EdgeInsets.fromLTRB(20, 0, 20, 8),
          child: Panel(
            color: kPrimarySoft,
            border: kPrimarySoft,
            child: Row(children: [
              ScaleIcon(size: 26),
              SizedBox(width: 10),
              Expanded(
                child: Text('You are #${myRank + 1} of ${rows.length} with ${s.xp} Scales',
                    style: TextStyle(fontWeight: FontWeight.w700, color: kPrimaryText)),
              ),
              TextButton(onPressed: () => _go(myRank ~/ perPage), child: Text('Find me')),
            ]),
          ),
        ),
        Expanded(
          child: PageView.builder(
            controller: _pages,
            itemCount: pageCount,
            onPageChanged: (p) => setState(() => _page = p),
            itemBuilder: (context, p) {
              final start = p * perPage;
              final slice = rows.sublist(start, (start + perPage).clamp(0, rows.length));
              return ListView(padding: EdgeInsets.symmetric(horizontal: 20), children: [
                for (final (i, r) in slice.indexed) _Row(rank: start + i + 1, name: r.$1, scales: r.$2, me: r.$1 == 'You'),
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
                Text('Ranks ${_page * perPage + 1}-${((_page + 1) * perPage).clamp(0, rows.length)} · demo players',
                    style: TextStyle(fontSize: 11, color: kMuted)),
              ]),
            ),
            IconButton(tooltip: 'Next page', onPressed: _page < pageCount - 1 ? () => _go(_page + 1) : null, icon: Icon(Icons.chevron_right)),
          ]),
        ),
      ]),
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
