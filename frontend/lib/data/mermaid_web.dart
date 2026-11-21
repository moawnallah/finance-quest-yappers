import 'dart:convert';
import 'dart:js_interop';
import 'dart:typed_data';

@JS('crocoMermaid.toPng')
external JSPromise<JSString> _toPng(JSString code, JSBoolean dark);

bool get mermaidSupported => true;

/// Parses and renders [code]; throws with Mermaid's error message when the
/// code is invalid, so the caller can ask the tutor for a repair.
Future<Uint8List> renderMermaid(String code, {bool dark = false}) async {
  try {
    final b64 = await _toPng(code.toJS, dark.toJS).toDart;
    return base64Decode(b64.toDart);
  } catch (e) {
    final msg = e.toString();
    throw FormatException(msg.length > 300 ? msg.substring(0, 300) : msg);
  }
}
