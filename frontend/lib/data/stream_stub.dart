bool get streamSupported => false;

Future<void> postStream(String url, Map<String, String> headers, String body, void Function(String line) onLine) async =>
    throw UnsupportedError('Streaming is used on the web build only.');
