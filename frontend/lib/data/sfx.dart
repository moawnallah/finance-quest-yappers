// Sound effects only, never background music. Short sounds generated for
// this app (assets/sfx, made by a script, no third-party audio):
// tick = the wheel passes a slice, whoosh = a page opens or closes,
// tap = switching tabs, correct / wrong = answer feedback, badge = a badge.
// Browsers only allow sound after the first tap, which the app always has.

import 'package:audioplayers/audioplayers.dart';

class Sfx {
  static bool enabled = true;
  static final List<AudioPlayer> _ticks = [];
  static int _next = 0;
  static DateTime _lastTick = DateTime(2000);

  static Future<void> _play(String name, {double volume = 0.6}) async {
    if (!enabled) return;
    try {
      final p = AudioPlayer()..setReleaseMode(ReleaseMode.release);
      await p.play(AssetSource('sfx/$name.wav'), volume: volume);
    } catch (_) {
      // Sound is a nice-to-have; never let it break the app.
    }
  }

  /// The wheel ticks: a few reused players so fast spins stay in time.
  static Future<void> tick() async {
    if (!enabled) return;
    final now = DateTime.now();
    if (now.difference(_lastTick).inMilliseconds < 45) return; // no machine-gun ticks
    _lastTick = now;
    try {
      if (_ticks.isEmpty) {
        for (var i = 0; i < 4; i++) {
          final p = AudioPlayer()..setReleaseMode(ReleaseMode.stop);
          await p.setSource(AssetSource('sfx/tick.wav'));
          _ticks.add(p);
        }
      }
      final p = _ticks[_next++ % _ticks.length];
      await p.stop();
      await p.setVolume(0.5);
      await p.resume();
    } catch (_) {}
  }

  static void whoosh() => _play('whoosh', volume: 0.35);
  static void tap() => _play('tap', volume: 0.4);
  static void correct() => _play('correct', volume: 0.55);
  static void wrong() => _play('wrong', volume: 0.5);
  static void badge() => _play('badge', volume: 0.6);
}
