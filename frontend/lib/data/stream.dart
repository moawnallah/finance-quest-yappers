// Streams NDJSON lines from a POST. Web: fetch() + ReadableStream (package:http
// buffers whole responses in the browser). Elsewhere: not supported, so the
// caller falls back to the non-streaming endpoint.
export 'stream_stub.dart' if (dart.library.js_interop) 'stream_web.dart';
