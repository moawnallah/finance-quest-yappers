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
  Future<String>? _pending;

  static const _tokenKey = 'fq_api_token';

  /// Returns a session token, creating one on the backend the first time.
  /// The token is kept on the device, so progress survives a reload.
  Future<String> _session(String name) {
    if (_token != null) return Future.value(_token!);
    return _pending ??= () async {
      try {
        final prefs = await SharedPreferences.getInstance();
        final saved = prefs.getString(_tokenKey);
        if (saved != null) return _token = saved;
        final r = await _send('POST', '/auth/session', body: {'display_name': name.isEmpty ? 'Learner' : name});
        _token = r['token'] as String;
        await prefs.setString(_tokenKey, _token!);
        return _token!;
      } finally {
        _pending = null;
      }
    }();
  }

  /// Create an account (POST /auth/register). Sends the current anonymous
  /// session, so progress made before signing up is kept.
  Future<Map<String, dynamic>> register(String email, String password, {String? displayName}) async {
    final prefs = await SharedPreferences.getInstance();
    final r = Map<String, dynamic>.from(await _send('POST', '/auth/register',
        body: {'email': email, 'password': password, if (displayName != null) 'display_name': displayName},
        token: _token ?? prefs.getString(_tokenKey)));
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
    final r = Map<String, dynamic>.from(await _authed('GET', '/me', name));
    return r['email'] == null ? null : r;
  }

  Future<void> _useToken(String t) async {
    _token = t;
    (await SharedPreferences.getInstance()).setString(_tokenKey, t);
  }

  /// Forget the session (sign-out), so the next call starts a new one.
  Future<void> reset() async {
    _token = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
  }

  Future<dynamic> _send(String method, String path, {Object? body, String? token, String? adminKey}) async {
    final uri = Uri.parse('$baseUrl$path');
    final headers = {
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

  Future<dynamic> _authed(String method, String path, String name, {Object? body}) async {
    try {
      return await _send(method, path, body: body, token: await _session(name));
    } on ApiException catch (e) {
      if (e.status != 401) rethrow;
      await reset(); // the backend lost the session (e.g. a fresh database): start a new one once
      return _send(method, path, body: body, token: await _session(name));
    }
  }

  /// Admin monitoring (GET /admin/...). The key travels in the X-Admin-Key
  /// header only, never in the URL.
  /// With [key] null, the signed-in admin account's own token is used.
  Future<Map<String, dynamic>> admin(String path, String? key) async =>
      Map<String, dynamic>.from(key == null ? await _authed('GET', '/admin/$path', 'Admin') : await _send('GET', '/admin/$path', adminKey: key));

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
    final token = await _session(name);
    String? text, mermaid;
    var fallback = false;
    await postStream(
      '$baseUrl/tutor/stream',
      {'Content-Type': 'application/json', 'Authorization': 'Bearer $token'},
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
  }) async =>
      Map<String, dynamic>.from(await _authed('POST', '/tasks/$taskId/attempts', name, body: {
        'response': response,
        if (reasons != null) 'reasons': reasons,
        if (confidence != null) 'confidence': confidence,
        'context': context,
        if (forNode != null) 'for_node': forNode,
        if (startedAt != null) 'started_at': startedAt.toUtc().toIso8601String(),
      }));
}
