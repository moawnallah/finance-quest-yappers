import 'dart:convert';
import 'dart:js_interop';
import 'package:web/web.dart' as web;

/// Downloads [text] as [filename] through a Blob URL and a temporary link. Returns true when started.
Future<bool> saveTextFile(String filename, String text, {String mimeType = 'text/csv'}) async {
  final bytes = utf8.encode(text);
  final blob = web.Blob([bytes.toJS].toJS, web.BlobPropertyBag(type: '$mimeType;charset=utf-8'));
  final url = web.URL.createObjectURL(blob);
  final a = web.HTMLAnchorElement()
    ..href = url
    ..download = filename
    ..style.display = 'none';
  web.document.body!.append(a);
  a.click();
  a.remove();
  Future.delayed(const Duration(seconds: 30), () => web.URL.revokeObjectURL(url));
  return true;
}
