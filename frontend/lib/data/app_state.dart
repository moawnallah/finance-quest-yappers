// App state for the draft. In the real app, scoring and unlocks move to the
// FastAPI backend (POST /answers) so the browser never sees correct answers.

import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart' show rootBundle;
import '../models/content.dart';
import 'api.dart';

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

/// Skills-tree panels in their teaching order (docs/skills_tree.md). The wheel
/// shows the panels that have skills.
const panelOrder = ['FOUNDATIONS', 'SAFETY', 'INSTRUMENTS', 'PORTFOLIO', 'DECISIONS', 'LONG HORIZON', 'PROTECTION'];
const panelLabels = {
  'FOUNDATIONS': 'Foundations',
  'SAFETY': 'Safety',
  'INSTRUMENTS': 'Instruments',
  'PORTFOLIO': 'Portfolio',
  'DECISIONS': 'Decisions',
  'LONG HORIZON': 'Long horizon',
  'PROTECTION': 'Protection',
};
const panelQuestions = {
  'FOUNDATIONS': 'How does money work over time?',
  'SAFETY': 'Am I protected before I invest?',
  'INSTRUMENTS': 'What am I buying, and what can go wrong?',
  'PORTFOLIO': 'How do I combine investments?',
  'DECISIONS': 'How do I decide on day X?',
  'LONG HORIZON': 'How do retirement and a mortgage change the plan?',
  'PROTECTION': 'Who is on my side, and who is not?',
};

class AppState extends ChangeNotifier {
  /// Backend client for the Skills screens (task engines). Scoring happens on the server.
  Api api = Api();
  Roadmap? roadmap;
  List<Question> placement = [];
  Map<String, String> placementTopic = {}; // question id -> topic
  Map<String, dynamic> bands = {}; // Eurobarometer score bands (pl / eu %)
  final Set<String> focusSlices = {}; // slices to highlight after placement

  /// Which wheel panel teaches each placement topic (docs/skills_tree.md:
  /// Q2 -> F3, Q3 -> F2, Q4 -> I3, Q5 -> I1, Q6 -> P1).
  static const topicSlice = {
    'compound interest': 'FOUNDATIONS',
    'inflation': 'FOUNDATIONS',
    'bonds': 'INSTRUMENTS',
    'risk and return': 'INSTRUMENTS',
    'diversification': 'PORTFOLIO',
  };

  // ---- Skills tree from the backend (GET /skills): the missions on the roadmaps.
  List<Map<String, dynamic>> skills = [];
  bool skillsLoading = false;
  String? skillsError;
  String selectedPanel = 'SAFETY';

  Future<void> loadSkills() async {
    skillsLoading = true;
    skillsError = null;
    notifyListeners();
    try {
      skills = await api.skills(profile.name);
      if (!panels.contains(selectedPanel) && panels.isNotEmpty) selectedPanel = startPanel ?? panels.first;
    } catch (e) {
      skillsError = '$e';
    } finally {
      skillsLoading = false;
      notifyListeners();
    }
  }

  List<String> get panels => [for (final p in panelOrder) if (skills.any((k) => k['panel'] == p)) p];
  List<Map<String, dynamic>> skillsIn(String panel) => [for (final k in skills) if (k['panel'] == panel) k];
  Map<String, dynamic>? skillById(String id) => skills.where((k) => k['id'] == id).firstOrNull;

  Map<String, dynamic> _st(Map<String, dynamic> k) => Map<String, dynamic>.from(k['status'] ?? {});
  bool skillDone(Map<String, dynamic> k) => _st(k)['done'] == true;
  int skillAnswered(Map<String, dynamic> k) => ((_st(k)['items_answered'] as num?) ?? 0).toInt();
  int skillTotal(Map<String, dynamic> k) => ((_st(k)['items_total'] as num?) ?? 0).toInt();

  /// 0..1: done = 1, otherwise scored questions answered / all scored questions.
  double skillProgress(Map<String, dynamic> k) {
    if (skillDone(k)) return 1;
    final total = skillTotal(k);
    return total == 0 ? 0 : (skillAnswered(k) / total).clamp(0, 1).toDouble();
  }

  /// Prerequisites that exist in the loaded tree (others are not published yet).
  List<String> knownAfter(Map<String, dynamic> k) => [for (final a in (k['after'] as List? ?? [])) if (skillById(a as String) != null) a];

  /// done | open | locked. Locked skills can still be started after a warning.
  String skillState(Map<String, dynamic> k) {
    if (skillDone(k)) return 'done';
    return knownAfter(k).every((a) => skillDone(skillById(a)!)) ? 'open' : 'locked';
  }

  double panelProgress(String panel) {
    final ks = skillsIn(panel);
    return ks.isEmpty ? 0 : ks.map(skillProgress).reduce((a, b) => a + b) / ks.length;
  }

  /// The panel with the first open, unfinished skill: where to start.
  String? get startPanel => panels.where((p) => skillsIn(p).any((k) => skillState(k) == 'open')).firstOrNull;

  void selectPanel(String p, {bool bySpin = true}) {
    if (p == selectedPanel && (!bySpin || wheelSpun)) return;
    selectedPanel = p;
    if (bySpin) wheelSpun = true;
    notifyListeners();
  }

  // ---- Badges: earning one queues it, and the shell shows a dialog.
  String? pendingBadge;
  void earn(String id) {
    if (badges.add(id)) {
      pendingBadge = id;
      notifyListeners();
    }
  }

  void clearPendingBadge() => pendingBadge = null;
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
    if (xpToday >= dailyGoal && badges.add('goal')) pendingBadge = 'goal';
    notifyListeners();
  }

  void completeNode(Node n, int correct) {
    final scored = n.questions.where((q) => q.isScored).length;
    if (doneNodes.add(n.id)) {
      if (badges.add('first_steps')) pendingBadge = 'first_steps';
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
    if (badges.add('placement')) {
      pendingBadge = 'placement';
      addXp(Rewards.quickCheck);
    }
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
  void signOut() { signedIn = false; profile.name = 'You'; api.reset(); notifyListeners(); }
  void markCoachSeen() { coachSeen = true; notifyListeners(); }
  void notify() => notifyListeners();
}
