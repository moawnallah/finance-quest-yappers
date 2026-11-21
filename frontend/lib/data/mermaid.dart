// Renders validated Mermaid code to PNG bytes. On the web it uses the pinned
// mermaid.js in web/index.html; elsewhere it reports "not supported" (the
// iPhone and Android builds need a web view for diagrams, not built yet).
export 'mermaid_stub.dart' if (dart.library.js_interop) 'mermaid_web.dart';
