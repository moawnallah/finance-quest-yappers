# frontend

Flutter cross-platform app: one Dart codebase that builds natively for iOS, Android, web and desktop (macOS, Windows, Linux). Owner: Michał.

- Demo targets: Flutter web (judges open a link or scan a QR code) and an Android build on a phone. iOS and desktop come from the same code later.
- Screens: login and onboarding, the investment wheel, a slice's roadmap tree, learning and quiz cards with the AI tutor, the time machine (play-money practice on real history), results with the first real step, progress, streaks and the A/B results page.
- API client: generate Dart models from the backend's OpenAPI spec, e.g. `openapi-generator-cli generate -i http://localhost:8000/openapi.json -g dart-dio -o lib/api`.
- Charts: a Flutter chart package (e.g. fl_chart) for the wheel and the time machine.
- Deploy: `flutter build web`, served from a small container on Cloud Run.
