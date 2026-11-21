import 'dart:convert';
import 'dart:js_interop';

@JS('crocoStream')
external JSPromise<JSAny?> _crocoStream(JSString url, JSString headers, JSString body, JSFunction onLine);

bool get streamSupported => true;

Future<void> postStream(String url, Map<String, String> headers, String body, void Function(String line) onLine) async {
  await _crocoStream(url.toJS, jsonEncode(headers).toJS, body.toJS, ((JSString l) => onLine(l.toDart)).toJS).toDart;
}
