// App state for the draft. In the real app, scoring and unlocks move to the
// FastAPI backend (POST /answers) so the browser never sees correct answers.

import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart' show rootBundle;
import '../models/content.dart';

class Profile {
  String name = 'Guest';
  String ageGroup = '30-49';
  String goal = 'Kids\' education';
  int horizonYears = 12;
  String experience = 'None';
  int confidenceBefore = 2;
  int? confidenceAfter;
  int? placementScore; // out of placementTotal
  int placementTotal = 5;
  int? retestScore; // same 5 questions repeated later
}

/// Level ladder (idea from Basis' career levels), with learning-themed names.
class Level {
  final String name;
  final int minXp;
  Level(this.name, this.minXp);
}

final levels = [Level('Explorer', 0), Level('Saver', 150), Level('Planner', 500), Level('Investor', 1200), Level('Mentor', 2500)];

/// Badges (idea from Basis and Finanz), each with a simple rule.
class BadgeDef {
  final String id, title, rule;
  BadgeDef(this.id, this.title, this.rule);
}

final badgeDefs = [
  BadgeDef('first_steps', 'First steps', 'Finish your first mission'),
  BadgeDef('placement', 'Know where you stand', 'Finish the quick check'),
  BadgeDef('daily', 'Daily thinker', 'Answer a daily scenario'),
  BadgeDef('calm', 'Stayed calm', 'Hold through a crash in the time machine'),
  BadgeDef('goal', 'Goal reached', 'Hit your daily XP goal'),
];

class AppState extends ChangeNotifier {
  Roadmap? roadmap;
  List<Question> placement = [];
  Map<String, String> placementTopic = {}; // question id -> topic
  Map<String, dynamic> bands = {}; // Eurobarometer score bands (pl / eu %)
  final Set<String> focusSlices = {}; // slices to highlight after placement

  /// Which wheel slice teaches each placement topic.
  static const topicSlice = {
    'compound interest': 'etfs',
    'inflation': 'money_market',
    'bonds': 'bonds',
    'risk and return': 'stocks',
    'diversification': 'mutual_and_index_funds',
  };
  final Profile profile = Profile();
  final Set<String> doneNodes = {};
  final Set<String> badges = {};
  int xp = 0;
  int xpToday = 0;
  int dailyGoal = 30;
  int streak = 0;
  bool dailyAnswered = false;
  bool largeText = false;
  bool listView = false;
  bool coachSeen = false;
  String themeMode = 'system'; // system | light | dark

  Future<void> load() async {
    final raw = await rootBundle.loadString('assets/roadmap.json');
    roadmap = Roadmap.fromJson(jsonDecode(raw));
    final bench = jsonDecode(await rootBundle.loadString('assets/eu_benchmark.json'));
    final quiz = bench['quiz'] as List;
    placement = quiz.map((e) => Question.fromJson(e)).toList();
    placementTopic = {for (final q in quiz) q['id'] as String: q['topic'] as String};
    bands = Map<String, dynamic>.from(bench['score_bands']);
    notifyListeners();
  }

  Level get level => levels.lastWhere((l) => xp >= l.minXp);
  Level? get nextLevel {
    final i = levels.indexOf(level);
    return i + 1 < levels.length ? levels[i + 1] : null;
  }

  // A node is unlocked when all nodes in `after` are done.
  bool isUnlocked(Node n) => n.after.every(doneNodes.contains);

  String nodeState(Node n) {
    if (doneNodes.contains(n.id)) return 'done';
    return isUnlocked(n) ? 'open' : 'locked';
  }

  double sliceProgress(Slice s) =>
      s.nodes.isEmpty ? 0 : s.nodes.where((n) => doneNodes.contains(n.id)).length / s.nodes.length;

  void addXp(int amount) {
    xp += amount;
    xpToday += amount;
    if (streak == 0 && amount > 0) streak = 1;
    if (xpToday >= dailyGoal) badges.add('goal');
    notifyListeners();
  }

  void completeNode(Node n, int correct) {
    if (doneNodes.add(n.id)) {
      badges.add('first_steps');
      addXp(10 * correct);
    }
  }

  void finishPlacement(int score, List<String> missedIds, {bool retest = false}) {
    if (retest) {
      profile.retestScore = score;
      notifyListeners();
      return;
    }
    focusSlices
      ..clear()
      ..addAll(missedIds.map((id) => topicSlice[placementTopic[id]]).whereType<String>());
    profile.placementScore = score;
    badges.add('placement');
    notifyListeners();
  }

  void answerDaily(bool correct) {
    if (dailyAnswered) return;
    dailyAnswered = true;
    badges.add('daily');
    addXp(correct ? 30 : 10);
  }

  void earnBadge(String id) { badges.add(id); notifyListeners(); }
  void setDailyGoal(int v) { dailyGoal = v; notifyListeners(); }
  void setLargeText(bool v) { largeText = v; notifyListeners(); }
  void setListView(bool v) { listView = v; notifyListeners(); }
  void setThemeMode(String m) { themeMode = m; notifyListeners(); }
  bool signedIn = false;
  void signIn(String name) { signedIn = true; profile.name = name; notifyListeners(); }
  void signOut() { signedIn = false; profile.name = 'Guest'; notifyListeners(); }
  void markCoachSeen() { coachSeen = true; notifyListeners(); }
  void notify() => notifyListeners();
}
