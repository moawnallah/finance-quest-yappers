// Content model matching content/roadmap.json (built by validate_content.py).

class Question {
  final String id;
  final String q;
  final List<String> options;
  final int? answer; // scored multiple choice when not null
  final String? why;
  final List<String>? feedback; // behaviour question: one feedback per option
  final List<String> sources;

  Question.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        q = j['q'],
        options = List<String>.from(j['options'] ?? []),
        answer = j['answer'],
        why = j['why'],
        feedback = j['feedback'] == null ? null : List<String>.from(j['feedback']),
        sources = List<String>.from(j['sources'] ?? []);

  bool get isScored => answer != null;
  bool get isBehaviour => feedback != null;
}

class Node {
  final String id;
  final String title;
  final List<String> after;
  final List<Question> questions;

  Node.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        title = j['title'],
        after = List<String>.from(j['after'] ?? []),
        questions = (j['questions'] as List).map((e) => Question.fromJson(e)).toList();
}

class Slice {
  final String key;
  final String label;
  final int risk; // 1 calm .. 5 bumpy
  final bool start; // recommended start (star)
  final List<Node> nodes;

  Slice.fromJson(Map<String, dynamic> j)
      : key = j['key'],
        label = j['label'],
        risk = j['risk'],
        start = j['start'] ?? false,
        nodes = (j['nodes'] as List).map((e) => Node.fromJson(e)).toList();
}

class Roadmap {
  final List<Slice> slices;
  Roadmap(this.slices);

  factory Roadmap.fromJson(Map<String, dynamic> j) {
    final order = List<String>.from(j['order']);
    final map = Map<String, dynamic>.from(j['slices']);
    return Roadmap(order.map((k) => Slice.fromJson(Map<String, dynamic>.from(map[k]))).toList());
  }

  Slice slice(String key) => slices.firstWhere((s) => s.key == key);
}
