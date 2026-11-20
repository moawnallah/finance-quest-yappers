import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../data/app_state.dart';

// Palette: light and dark values, switched by [appDark] (set from the theme).
bool appDark = false;
Color _p(int light, int dark) => Color(appDark ? dark : light);
Color get kInk => _p(0xFF101828, 0xFFF2F4F7);
Color get kMuted => _p(0xFF475467, 0xFFB4BCCB);
Color get kBody => _p(0xFF344054, 0xFFD0D5DD);
Color get kFaint => _p(0xFF98A2B3, 0xFF8A93A6);
const kPrimary = Color(0xFF3B4FD8);
Color get kPrimaryText => _p(0xFF2A3AA8, 0xFFA9B6FF);
Color get kPrimarySoft => _p(0xFFEEF0FD, 0xFF232A55);
Color get kGreen => _p(0xFF067647, 0xFF4ADE80);
Color get kGreenSoft => _p(0xFFECFDF3, 0xFF12301F);
Color get kRed => _p(0xFFB42318, 0xFFF87171);
Color get kRedSoft => _p(0xFFFEF3F2, 0xFF3A1717);
Color get kBg => _p(0xFFF6F7F9, 0xFF0F1320);
Color get kSurface => _p(0xFFFFFFFF, 0xFF171C2C);
Color get kLine => _p(0xFFEAECF0, 0xFF2A3146);
Color get kBorder => _p(0xFFD0D5DD, 0xFF3A425C);
Color get kTutorBorder => _p(0xFFC7CDF7, 0xFF3B4795);
Color get kWarnSoft => _p(0xFFFFFAEB, 0xFF2E2510);
Color get kWarnBorder => _p(0xFFFDE68A, 0xFF6B5418);
Color get kWarnText => _p(0xFF93370D, 0xFFFCD34D);
Color get kWarnIcon => _p(0xFFB54708, 0xFFF59E0B);

/// Risk colour scale: 1 calm (green) .. 5 bumpy (dark red).
Color riskColor(int risk) => [
      Color(0xFF1F7A55), Color(0xFF3D8B5E), Color(0xFF8A7A1E), Color(0xFFB8551A), Color(0xFF7F1D1D)
    ][(risk - 1).clamp(0, 4)];

/// Top bar with streak and XP chips, shared by most screens.
class StatsBar extends StatelessWidget implements PreferredSizeWidget {
  final String title;
  final String? subtitle;
  StatsBar({super.key, required this.title, this.subtitle});

  @override
  Size get preferredSize => Size.fromHeight(72);

  @override
  Widget build(BuildContext context) {
    final s = context.watch<AppState>();
    return AppBar(
      backgroundColor: kBg,
      toolbarHeight: 72,
      titleSpacing: 20,
      title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        if (subtitle != null) Text(subtitle!, style: TextStyle(fontSize: 13, color: kMuted)),
        Text(title, style: TextStyle(fontWeight: FontWeight.w700, fontSize: 22)),
      ]),
      actions: [
        _Chip(icon: Icons.local_fire_department, color: kWarnIcon, label: '${s.streak}'),
        SizedBox(width: 6),
        _Chip(icon: Icons.star, color: kPrimary, label: '${s.xp} XP'),
        SizedBox(width: 16),
      ],
    );
  }
}

class _Chip extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String label;
  _Chip({required this.icon, required this.color, required this.label});

  @override
  Widget build(BuildContext context) => Container(
        padding: EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
            color: kSurface, borderRadius: BorderRadius.circular(999), border: Border.all(color: kLine)),
        child: Row(children: [Icon(icon, size: 16, color: color), SizedBox(width: 4), Text(label, style: TextStyle(fontWeight: FontWeight.w600))]),
      );
}

/// Rounded white card used for panels.
class Panel extends StatelessWidget {
  final Widget child;
  final Color? color;
  final Color? border;
  Panel({super.key, required this.child, this.color, this.border});

  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: color ?? kSurface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: border ?? kLine),
        ),
        child: child,
      );
}

/// The AI tutor bubble. In the real app the text comes from POST /tutor
/// (Gemini, education only, labelled as AI); here it shows the stored "why".
class TutorBubble extends StatelessWidget {
  final String text;
  TutorBubble({super.key, required this.text});

  @override
  Widget build(BuildContext context) => Panel(
        border: kTutorBorder,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Container(
              padding: EdgeInsets.all(4),
              decoration: BoxDecoration(color: kPrimary, borderRadius: BorderRadius.circular(6)),
              child: Icon(Icons.auto_awesome, size: 14, color: Colors.white),
            ),
            SizedBox(width: 8),
            Text('AI tutor', style: TextStyle(fontWeight: FontWeight.w700, color: kPrimaryText)),
            Spacer(),
            Text('Educational, not advice', style: TextStyle(fontSize: 11, color: kMuted)),
          ]),
          SizedBox(height: 6),
          Text(text, style: TextStyle(height: 1.45, color: kBody)),
        ]),
      );
}
