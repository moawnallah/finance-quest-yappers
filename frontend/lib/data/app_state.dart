// App state for the draft. In the real app, scoring and unlocks move to the
// FastAPI backend (POST /answers) so the browser never sees correct answers.

import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart' show rootBundle;
import '../models/content.dart';

class Profile {
  String name = 'You';
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

final levels = [Level('Beginner', 0), Level('Intermediate', 300), Level('Expert', 1000)];

/// Plain names for the 1-5 risk scale (how bumpy the ride is).
const riskNames = ['Calm', 'Steady', 'Balanced', 'Bumpy', 'Wild'];
String riskName(int r) => riskNames[(r - 1).clamp(0, 4)];

/// How Scales (the CrocoCash points) are earned. One points type, given only
/// for a clear action or result.
class Rewards {
  static const correctAnswer = 10;
  static const missionDone = 20;
  static const dailyRight = 15;
  static const dailyTried = 5;
  static const quickCheck = 25;
}

/// Badges (idea from Basis and Finanz), each with a simple rule.
class BadgeDef {
  final String id, title, rule;
  BadgeDef(this.id, this.title, this.rule);
}

final badgeDefs = [
  BadgeDef('first_steps', 'First mission', 'Finish your first mission'),
  BadgeDef('placement', 'Quick check', 'Finish the quick check'),
  BadgeDef('goal', 'Daily goal', 'Reach your daily Scales goal'),
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
  final Map<String, int> nodeAnswered = {}; // node id -> questions answered so far
  String selectedSlice = 'bonds'; // the topic at the top of the home wheel
  bool wheelSpun = false; // hides the "spin me" hint after the first spin
  final Set<String> badges = {};
  int xp = 0;
  int xpToday = 0;
  int dailyGoal = 50;
  (int correct, int total, int earned)? lastMission; // for the result screen
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

  /// 0..1 for one mission: done = 1, otherwise answered questions / all questions.
  double nodeProgress(Node n) {
    if (doneNodes.contains(n.id)) return 1;
    if (n.questions.isEmpty) return 0;
    return ((nodeAnswered[n.id] ?? 0) / n.questions.length).clamp(0, 1).toDouble();
  }

  /// 0..1 for a whole slice: the average of its missions' progress.
  double sliceProgress(Slice s) =>
      s.nodes.isEmpty ? 0 : s.nodes.map(nodeProgress).reduce((a, b) => a + b) / s.nodes.length;

  void recordAnswer(Node n, int questionIndex) {
    final now = questionIndex + 1;
    if (now > (nodeAnswered[n.id] ?? 0)) {
      nodeAnswered[n.id] = now;
      notifyListeners();
    }
  }

  void selectSlice(String key, {bool bySpin = false}) {
    if (key == selectedSlice && (!bySpin || wheelSpun)) return;
    selectedSlice = key;
    if (bySpin) wheelSpun = true;
    notifyListeners();
  }

  void addXp(int amount) {
    xp += amount;
    xpToday += amount;
    if (streak == 0 && amount > 0) streak = 1;
    if (xpToday >= dailyGoal) badges.add('goal');
    notifyListeners();
  }

  void completeNode(Node n, int correct) {
    final scored = n.questions.where((q) => q.isScored).length;
    if (doneNodes.add(n.id)) {
      badges.add('first_steps');
      final earned = Rewards.correctAnswer * correct + Rewards.missionDone;
      lastMission = (correct, scored, earned);
      addXp(earned);
    } else {
      lastMission = (correct, scored, 0); // replays earn nothing extra
      notifyListeners();
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
    if (badges.add('placement')) addXp(Rewards.quickCheck);
    notifyListeners();
  }

  void answerDaily(bool correct) {
    if (dailyAnswered) return;
    dailyAnswered = true;
    addXp(correct ? Rewards.dailyRight : Rewards.dailyTried);
  }

  void earnBadge(String id) { badges.add(id); notifyListeners(); }
  void setDailyGoal(int v) { dailyGoal = v; notifyListeners(); }
  void setLargeText(bool v) { largeText = v; notifyListeners(); }
  void setListView(bool v) { listView = v; notifyListeners(); }
  void setThemeMode(String m) { themeMode = m; notifyListeners(); }
  bool signedIn = false;
  void signIn(String name) { signedIn = true; profile.name = name; notifyListeners(); }
  void signOut() { signedIn = false; profile.name = 'You'; notifyListeners(); }
  void markCoachSeen() { coachSeen = true; notifyListeners(); }
  void notify() => notifyListeners();
}
