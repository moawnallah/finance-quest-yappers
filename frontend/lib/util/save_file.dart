// Save a text file to the user's device: a real browser download on the web, the share/clipboard
// fallback elsewhere. Opening a data: URL in a new tab does not work: browsers block it silently.
export 'save_file_stub.dart' if (dart.library.js_interop) 'save_file_web.dart';
