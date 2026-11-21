import 'package:flutter/services.dart';

/// Outside the web there is no download folder to write to here: copy the text so it can be pasted.
Future<bool> saveTextFile(String filename, String text, {String mimeType = 'text/csv'}) async {
  await Clipboard.setData(ClipboardData(text: text));
  return false;
}
