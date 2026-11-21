import 'dart:typed_data';

bool get mermaidSupported => false;

Future<Uint8List> renderMermaid(String code, {bool dark = false}) async =>
    throw UnsupportedError('Diagrams are shown in the web version for now.');
