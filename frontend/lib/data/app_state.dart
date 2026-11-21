// App state for the draft. In the real app, scoring and unlocks move to the
// FastAPI backend (POST /answers) so the browser never sees correct answers.

import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:shared_preferences/shared_preferences.dart';
import '../models/content.dart';
import 'api.dart';
import 'sfx.dart';

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

/// What the tutor chat knows when it is opened from a question.
class TutorContext {
  final String? node, taskId;
  final String question;
  final String? picked, correct, explanation;
  final bool? wasRight;
  TutorContext({this.node, this.taskId, required this.question, this.picked, this.correct, this.explanation, this.wasRight});
  Map<String, dynamic> toJson() => {
        'node': node, 'task_id': taskId, 'question': question, 'picked': picked,
        'correct': correct, 'explanation': explanation, 'was_right': wasRight,
      };
  static TutorContext? fromJson(Map<String, dynamic>? j) => j == null
      ? null
      : TutorContext(
          node: j['node'], taskId: j['task_id'], question: j['question'] ?? '', picked: j['picked'],
          correct: j['correct'], explanation: j['explanation'], wasRight: j['was_right']);
}

/// One message in a tutor conversation. [image] is a rendered chart.
class TutorMessage {
  final bool mine;
  String text; // grows while the reply streams in
  Uint8List? image;
  bool drawing = false;
  TutorMessage(this.mine, this.text);
}

/// A tutor conversation: its messages and, when opened from a question, that
/// question's context. Kept in memory for now (lost on reload).
class TutorConversation {
  final String id;
  String title;
  final DateTime started = DateTime.now();
  final TutorContext? context;
  final List<TutorMessage> messages = [];
  bool titled = false; // a real title was generated or set by the user
  TutorConversation({required this.id, required this.title, this.context});
}

class AppState extends ChangeNotifier {
  TutorContext? tutorContext;
  final List<TutorConversation> conversations = [];
  String? activeConversation;
  int _convSeq = 0;

  TutorConversation newConversation({TutorContext? context}) {
    if (context == null) {
      final empty = conversations.where((c) => c.context == null && !c.messages.any((m) => m.mine)).firstOrNull;
      if (empty != null) {
        activeConversation = empty.id;
        notifyListeners();
        return empty;
      }
    }
    final c = TutorConversation(id: 'c${DateTime.now().microsecondsSinceEpoch}${++_convSeq}', title: context?.question ?? 'New chat', context: context);
    conversations.insert(0, c);
    activeConversation = c.id;
    notifyListeners();
    saveConversations();
    return c;
  }

  // Conversations are saved on this device per account, so they survive a page
  // refresh and signing out and back in. Charts are re-drawn from text only.
  String get _convKey => 'tutor_conversations';

  Future<void> saveConversations() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_convKey, jsonEncode([
        for (final c in conversations.where((c) => c.messages.any((m) => m.mine)).take(30))
          {
            'id': c.id, 'title': c.title, 'titled': c.titled, 'context': c.context?.toJson(),
            'messages': [for (final m in c.messages) {'mine': m.mine, 'text': m.text}],
          }
      ]));
      await prefs.setString('tutor_active', activeConversation ?? '');
    } catch (_) {}
  }

  bool conversationsLoaded = false;

  Future<void> loadConversations() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_convKey);
      conversations.clear();
      if (raw != null) {
        for (final j in (jsonDecode(raw) as List).cast<Map<String, dynamic>>()) {
          final c = TutorConversation(id: j['id'], title: j['title'] ?? 'Chat', context: TutorContext.fromJson(j['context']))
            ..titled = j['titled'] == true;
          for (final m in (j['messages'] as List).cast<Map<String, dynamic>>()) {
            c.messages.add(TutorMessage(m['mine'] == true, m['text'] ?? ''));
          }
          conversations.add(c);
        }
      }
      final a = prefs.getString('tutor_active');
      activeConversation = conversations.any((c) => c.id == a) ? a : conversations.firstOrNull?.id;
    } catch (_) {}
    conversationsLoaded = true;
    notifyListeners();
  }

  TutorConversation? get currentConversation => conversations.where((c) => c.id == activeConversation).firstOrNull;
  void openConversation(String id) {
    activeConversation = id;
    notifyListeners();
    saveConversations();
  }

  void renameConversation(String id, String title) {
    final t = title.trim();
    final c = conversations.where((c) => c.id == id).firstOrNull;
    if (c == null || t.isEmpty) return;
    c.title = t.length > 60 ? t.substring(0, 60) : t;
    c.titled = true;
    notifyListeners();
    saveConversations();
  }

  void deleteConversation(String id) {
    conversations.removeWhere((c) => c.id == id);
    if (activeConversation == id) activeConversation = conversations.firstOrNull?.id;
    notifyListeners();
    saveConversations();
  }
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

  /// All seven skills-tree panels, always shown on the wheel; the ones without
  /// published skills yet appear as "coming soon".
  List<String> get panels => skills.isEmpty ? [] : panelOrder;
  bool panelReady(String p) => skills.any((k) => k['panel'] == p);
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
  /// Confidence vs correctness: one point per finished mission run, with the
  /// average "How sure are you?" answer (1-5) and the average score (0-1).
  final List<(String, double, double)> calibration = [];
  void addCalibration(String title, double confidence, double score) {
    calibration.add((title, confidence, score));
    notifyListeners();
  }

  /// Questions finished per mission, so leaving and coming back resumes.
  final Map<String, Set<String>> answeredInMission = {};
  void markAnswered(String skill, String taskId) => answeredInMission.putIfAbsent(skill, () => {}).add(taskId);

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
  bool wheelNudged = false; // the hint wiggle plays once per visit, not on every tab switch
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
    await loadConversations();
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
  bool soundOn = true;
  void setSound(bool v) { soundOn = v; Sfx.enabled = v; notifyListeners(); }
  void setListView(bool v) { listView = v; notifyListeners(); }
  void setThemeMode(String m) { themeMode = m; notifyListeners(); }
  bool signedIn = false;
  void signIn(String name) {
    signedIn = true;
    profile.name = name;
    notifyListeners();
    loadConversations();
  }

  /// Admin emails (build setting ADMIN_EMAILS, comma separated). Signing in
  /// with one shows the admin panel. Demo only: the backend must check this too.
  static const adminEmails = String.fromEnvironment('ADMIN_EMAILS', defaultValue: 'admin@crococash.xyz');
  String? email;
  bool isAdmin = false;
  bool guest = false;

  void signInWithEmail(String e) {
    email = e.toLowerCase();
    isAdmin = adminEmails.split(',').map((x) => x.trim().toLowerCase()).contains(email);
    guest = false;
    signInMethod = 'email';
    signIn(e.split('@').first);
  }

  void signInAsGuest() {
    guest = true;
    signInMethod = 'guest';
    isAdmin = false;
    signedIn = false;
    profile.name = 'Guest';
    notifyListeners();
    loadConversations();
  }
  /// How the user signed in: email | google | guest (null before sign-in).
  String? signInMethod;

  void signOut() {
    signedIn = false;
    guest = false;
    isAdmin = false;
    email = null;
    signInMethod = null;
    profile.name = 'You';
    api.reset();
    notifyListeners();
  }

  void rename(String name) {
    final n = name.trim();
    if (n.isEmpty) return;
    profile.name = n.length > 30 ? n.substring(0, 30) : n;
    notifyListeners();
  }
  void markCoachSeen() { coachSeen = true; notifyListeners(); }
  void notify() => notifyListeners();
}
