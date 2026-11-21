import 'dart:math';
// Client for the Finance Quest backend (FastAPI, backend/app). Used by the Skills screens,
// which run on the task engines: the backend scores every answer, so correct answers,
// truth values and reason weights reach the app only after a submission.
//
// The backend URL is set at build time:
//   flutter run -d chrome --dart-define=API_URL=http://localhost:8001
//   flutter build web --release --dart-define=API_URL=https://<your-backend>

import 'dart:convert';

import 'package:http/http.dart' as http;
import 'stream.dart';
import 'package:shared_preferences/shared_preferences.dart';

const apiUrl = String.fromEnvironment('API_URL', defaultValue: 'http://localhost:8001');

class ApiException implements Exception {
  final int status;
  final String code;
  final String message;
  ApiException(this.status, this.code, this.message);
  @override
  String toString() => message;
}

class Api {
  Api({http.Client? client, this.baseUrl = apiUrl}) : _http = client ?? http.Client();

  final http.Client _http;
  final String baseUrl;
  String? _token;

  static const _tokenKey = 'fq_api_token';

  /// Guests are stateless: no session on the server. The app keeps their id (for stable question
  /// draws), their answer history and their survey here, and sends what a request needs in
  /// headers (X-Guest-Id, X-Guest-History). Only accounts have a token.
  static const _guestIdKey = 'fq_guest_id', _guestHistoryKey = 'fq_guest_history', _guestSurveyKey = 'fq_guest_survey';
  String? _guestId;
  List<dynamic> guestHistory = [];
  Map<String, dynamic>? guestSurvey;
  String? guestChosenPath;
  bool _loaded = false;

  bool get isGuest => _token == null;

  Future<void> _load() async {
    if (_loaded) return;
    _loaded = true;
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString(_tokenKey);
    _guestId = prefs.getString(_guestIdKey);
    if (_guestId == null) {
      final r = Random.secure();
      _guestId = List.generate(24, (_) => '0123456789abcdef'[r.nextInt(16)]).join();
      await prefs.setString(_guestIdKey, _guestId!);
    }
    try {
      guestHistory = jsonDecode(prefs.getString(_guestHistoryKey) ?? '[]') as List;
      final sv = prefs.getString(_guestSurveyKey);
      if (sv != null) {
        final m = jsonDecode(sv) as Map<String, dynamic>;
        guestSurvey = Map<String, dynamic>.from(m['survey'] as Map);
        guestChosenPath = m['chosen'] as String?;
      }
    } catch (_) {
      guestHistory = [];
    }
  }

  Future<void> _saveGuest() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_guestHistoryKey, jsonEncode(guestHistory));
    if (guestSurvey != null) await prefs.setString(_guestSurveyKey, jsonEncode({'survey': guestSurvey, 'chosen': guestChosenPath}));
  }

  Map<String, String> get _guestHeaders => {'X-Guest-Id': _guestId ?? 'guest', 'X-Guest-History': jsonEncode(guestHistory)};

  /// Forget everything a guest kept (new guest, or the start of an account: nothing carries over).
  Future<void> clearGuest() async {
    guestHistory = [];
    guestSurvey = null;
    guestChosenPath = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_guestHistoryKey);
    await prefs.remove(_guestSurveyKey);
  }

  /// Create an account (POST /auth/register). Sends the current anonymous
  /// session, so progress made before signing up is kept.
  Future<Map<String, dynamic>> register(String email, String password, {String? displayName}) async {
    final prefs = await SharedPreferences.getInstance();
    final r = Map<String, dynamic>.from(await _send('POST', '/auth/register',
        body: {'email': email, 'password': password, if (displayName != null) 'display_name': displayName}));
    await _useToken(r['token'] as String);
    return r;
  }

  /// Sign in (POST /auth/login); the account's token replaces the anonymous one.
  Future<Map<String, dynamic>> login(String email, String password) async {
    final r = Map<String, dynamic>.from(await _send('POST', '/auth/login', body: {'email': email, 'password': password}));
    await _useToken(r['token'] as String);
    return r;
  }

  /// The signed-in account (GET /me), or null for an anonymous session.
  Future<Map<String, dynamic>?> account(String name) async {
    await _load();
    if (isGuest) return null;
    final r = Map<String, dynamic>.from(await _authed('GET', '/me', name));
    return r['email'] == null ? null : r;
  }

  Future<void> _useToken(String t) async {
    _token = t;
    (await SharedPreferences.getInstance()).setString(_tokenKey, t);
    await clearGuest(); // an account starts fresh
  }

  /// Forget the session (sign-out), so the next call starts a new one.
  Future<void> reset() async {
    _token = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
    await clearGuest();
  }

  Future<dynamic> _send(String method, String path,
      {Object? body, String? token, String? adminKey, Map<String, String> extra = const {}}) async {
    final uri = Uri.parse('$baseUrl$path');
    final headers = {
      ...extra,
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
      if (adminKey != null) 'X-Admin-Key': adminKey,
    };
    final http.Response r;
    try {
      r = method == 'GET'
          ? await _http.get(uri, headers: headers)
          : await _http.post(uri, headers: headers, body: jsonEncode(body ?? {}));
    } catch (e) {
      throw ApiException(0, 'offline', 'Cannot reach the server at $baseUrl. Is the backend running?');
    }
    final data = r.body.isEmpty ? null : jsonDecode(utf8.decode(r.bodyBytes));
    if (r.statusCode >= 400) {
      final err = data is Map ? data['error'] : null;
      throw ApiException(r.statusCode, err?['code'] ?? 'http_${r.statusCode}', err?['message'] ?? 'Request failed (${r.statusCode})');
    }
    return data;
  }

  /// An account request (Bearer token), or a guest request with the guest headers.
  Future<dynamic> _authed(String method, String path, String name, {Object? body, Map<String, String> extra = const {}}) async {
    await _load();
    if (isGuest) return _send(method, path, body: body, extra: {..._guestHeaders, ...extra});
    try {
      return await _send(method, path, body: body, token: _token, extra: extra);
    } on ApiException catch (e) {
      if (e.status != 401) rethrow;
      await reset(); // the token is no longer valid (e.g. an old guest session): continue as a guest
      return _send(method, path, body: body, extra: {..._guestHeaders, ...extra});
    }
  }

  /// Admin monitoring (GET /admin/...). The key travels in the X-Admin-Key
  /// header only, never in the URL.
  /// With [key] null, the signed-in admin account's own token is used.
  Future<Map<String, dynamic>> admin(String path, String? key) async =>
      Map<String, dynamic>.from(key == null ? await _authed('GET', '/admin/$path', 'Admin') : await _send('GET', '/admin/$path', adminKey: key));

  /// Admin changes (PATCH /admin/feedback/{id}, ...), with the key or the admin account's token.
  Future<Map<String, dynamic>> adminWrite(String method, String path, Object? body, String? key) async =>
      Map<String, dynamic>.from(key == null
          ? await _authed(method, '/admin/$path', 'Admin', body: body)
          : await _send(method, '/admin/$path', body: body, adminKey: key));

  /// The AI tutor (POST /tutor, docs/tutor_agent.md section 5). Returns the
  /// tutor's text. Throws when the backend has no tutor yet; the app then
  /// answers from the stored explanation.
  Future<({String text, String? mermaid})> tutor(String name,
      {required String mode, required String message, Map<String, dynamic>? context, List<Map<String, String>> history = const []}) async {
    final r = Map<String, dynamic>.from(await _authed('POST', '/tutor', name, body: {'mode': mode, 'message': message, 'context': context, 'history': history}));
    if (r['fallback'] == true) throw ApiException(503, 'tutor_unavailable', (r['text'] as String?) ?? '');
    return (text: (r['text'] as String?) ?? '', mermaid: r['mermaid'] as String?);
  }

  /// The tutor, streamed (POST /tutor/stream): onDelta gets each piece of text
  /// as the model writes it; the result is the final text and checked diagram.
  Future<({String text, String? mermaid})> tutorStream(String name,
      {required String mode, required String message, Map<String, dynamic>? context,
      List<Map<String, String>> history = const [], required void Function(String) onDelta}) async {
    await _load();
    final auth = isGuest ? _guestHeaders : {'Authorization': 'Bearer $_token'};
    String? text, mermaid;
    var fallback = false;
    await postStream(
      '$baseUrl/tutor/stream',
      {'Content-Type': 'application/json', ...auth},
      jsonEncode({'mode': mode, 'message': message, 'context': context, 'history': history}),
      (line) {
        final m = jsonDecode(line) as Map<String, dynamic>;
        if (m['t'] == 'delta') onDelta(m['text'] as String);
        if (m['t'] == 'done') {
          text = m['text'] as String?;
          mermaid = m['mermaid'] as String?;
          fallback = m['fallback'] == true;
        }
      },
    );
    if (text == null) throw ApiException(0, 'stream', 'The reply stopped early.');
    if (fallback) throw ApiException(503, 'tutor_unavailable', text!);
    return (text: text!, mermaid: mermaid);
  }

  // ---------- skills (task engines) ----------

  /// Scales kept on the server (GET /me/scales) and the rewards earned outside a task.
  /// Guests keep their Scales in the app only.
  Future<Map<String, dynamic>> scales(String name) async {
    await _load();
    return isGuest ? {} : Map<String, dynamic>.from(await _authed('GET', '/me/scales', name));
  }

  Future<Map<String, dynamic>> awardScales(String name, String source) async {
    await _load();
    return isGuest ? {} : Map<String, dynamic>.from(await _authed('POST', '/me/scales', name, body: {'source': source}));
  }

  /// The starting survey for the backend router (POST /onboarding) and the path it recommends.
  Future<Map<String, dynamic>> onboarding(String name, Map<String, dynamic> survey) async {
    final r = Map<String, dynamic>.from(await _authed('POST', '/onboarding', name, body: survey));
    if (isGuest) {
      guestSurvey = survey; // guests keep their survey; the Path tab sends it back (POST /path/preview)
      guestChosenPath = null;
      await _saveGuest();
    }
    return r;
  }

  Future<Map<String, dynamic>> path(String name) async {
    await _load();
    if (!isGuest) return Map<String, dynamic>.from(await _authed('GET', '/me/path', name));
    if (guestSurvey == null) return {'survey_done': false, 'steps': [], 'challenges': []};
    return Map<String, dynamic>.from(await _authed('POST', '/path/preview', name,
        body: {'survey': guestSurvey, if (guestChosenPath != null) 'chosen_path': guestChosenPath}));
  }

  Future<Map<String, dynamic>> choosePath(String name, String id) async {
    await _load();
    if (isGuest) {
      guestChosenPath = id;
      await _saveGuest();
      return {'path_id': id};
    }
    return Map<String, dynamic>.from(await _authed('POST', '/onboarding/choose-path', name, body: {'path_id': id}));
  }

  /// The end-of-path check-in (POST /paths/finish): thanks, the other path and next_steps.
  Future<Map<String, dynamic>> finishPath(String name, Map<String, dynamic> body) async {
    await _load();
    return Map<String, dynamic>.from(await _authed('POST', '/paths/finish', name,
        body: {...body, if (isGuest && guestSurvey != null) 'survey': guestSurvey}));
  }

  /// Every node of the skills tree, built or planned (GET /roadmap).
  Future<List<Map<String, dynamic>>> roadmap(String name) async =>
      ((await _authed('GET', '/roadmap', name))['nodes'] as List).cast<Map<String, dynamic>>();

  /// Hard tasks: run the public tests on the code panel's text (nothing is scored).
  Future<Map<String, dynamic>> runHard(String name, String taskId, String code) async =>
      Map<String, dynamic>.from(await _authed('POST', '/tasks/$taskId/run', name, body: {'code': code}));

  /// Real leagues per level, ranked by Scales.
  Future<Map<String, dynamic>> leagues(String name, {int guestScales = 0}) async =>
      Map<String, dynamic>.from(await _authed('GET', '/leagues', name, extra: {'X-Guest-Scales': '$guestScales'}));

  Future<List<Map<String, dynamic>>> skills(String name) async =>
      [for (final s in await _authed('GET', '/skills', name) as List) Map<String, dynamic>.from(s)];

  Future<Map<String, dynamic>> skill(String name, String nodeId) async =>
      Map<String, dynamic>.from(await _authed('GET', '/skills/$nodeId', name));

  /// context: 'prerequisite-test' or 'test-out'
  Future<Map<String, dynamic>> drawnTest(String name, String nodeId, String context) async =>
      Map<String, dynamic>.from(await _authed('GET', '/skills/$nodeId/$context', name));

  Future<Map<String, dynamic>> task(String name, String taskId) async =>
      Map<String, dynamic>.from(await _authed('GET', '/tasks/$taskId', name));

  Future<Map<String, dynamic>> submit(
    String name,
    String taskId, {
    required Object? response,
    List<String>? reasons,
    int? confidence,
    String context = 'practice',
    String? forNode,
    DateTime? startedAt,
  }) async {
    final r = Map<String, dynamic>.from(await _authed('POST', '/tasks/$taskId/attempts', name, body: {
      'response': response,
      if (reasons != null) 'reasons': reasons,
      if (confidence != null) 'confidence': confidence,
      'context': context,
      if (forNode != null) 'for_node': forNode,
      if (startedAt != null) 'started_at': startedAt.toUtc().toIso8601String(),
    }));
    if (isGuest && r['record'] is List) {
      guestHistory = [...guestHistory, r['record']]; // the server stored nothing; the app keeps it
      await _saveGuest();
    }
    return r;
  }
}
