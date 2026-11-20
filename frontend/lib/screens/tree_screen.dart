// A slice's roadmap: nodes in order, locked until their `after` nodes are done.
// Shown as a vertical path; a graph layout can replace this later.

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';
import '../widgets/common.dart';

class TreeScreen extends StatelessWidget {
  final String sliceKey;
  TreeScreen({super.key, required this.sliceKey});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    final slice = s.roadmap!.slice(sliceKey);
    return Scaffold(
      appBar: StatsBar(title: slice.label, subtitle: 'Roadmap'),
      body: ListView(padding: EdgeInsets.all(20), children: [
        Panel(
          child: Row(children: [
            Container(width: 36, height: 36, decoration: BoxDecoration(color: riskColor(slice.risk), borderRadius: BorderRadius.circular(10))),
            SizedBox(width: 12),
            Expanded(
              child: Text('${riskName(slice.risk)} ride · ${(s.sliceProgress(slice) * 100).round()}% done',
                  style: TextStyle(fontWeight: FontWeight.w600)),
            ),
          ]),
        ),
        SizedBox(height: 16),
        for (final (i, n) in slice.nodes.indexed) ...[
          if (i > 0) Padding(padding: EdgeInsets.only(left: 27), child: SizedBox(height: 18, child: VerticalDivider(width: 2, thickness: 2))),
          _NodeTile(
            title: n.title,
            state: s.nodeState(n),
            lockReason: n.after.isEmpty ? null : 'Finish ${n.after.map((a) => slice.nodes.firstWhere((x) => x.id == a).title).join(' and ')} first',
            onTap: s.nodeState(n) == 'locked' ? null : () => context.push('/mission/$sliceKey/${Uri.encodeComponent(n.id)}'),
          ),
        ],
      ]),
    );
  }
}

class _NodeTile extends StatelessWidget {
  final String title;
  final String state;
  final String? lockReason;
  final VoidCallback? onTap;
  _NodeTile({required this.title, required this.state, this.lockReason, this.onTap});

  @override
  Widget build(BuildContext context) {
    final done = state == 'done', locked = state == 'locked';
    final color = done ? kGreen : locked ? kFaint : kPrimary;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Panel(
        border: locked ? null : color,
        child: Row(children: [
          CircleAvatar(
            radius: 20,
            backgroundColor: locked ? kLine : color,
            child: Icon(done ? Icons.check : locked ? Icons.lock : Icons.play_arrow, color: locked ? kFaint : Colors.white),
          ),
          SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: TextStyle(fontWeight: FontWeight.w600, color: locked ? kMuted : kInk)),
              Text(done ? 'Done' : locked ? (lockReason ?? 'Locked') : '5-minute mission',
                  style: TextStyle(fontSize: 13, color: kMuted)),
            ]),
          ),
        ]),
      ),
    );
  }
}
