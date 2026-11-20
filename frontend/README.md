# frontend

The Flutter app for Finance Quest: one Dart codebase for web, Android, iOS and desktop. Owner: Michał.

Live draft: https://finance-quest-draft.vercel.app

## Run it locally

**What you need**
- Flutter 3.50 or newer (stable channel). Check with `flutter --version`.
- Google Chrome for the web build. Android Studio or Xcode only if you want a phone build.

**Steps**
1. Go to this folder: `cd frontend`
2. Install packages: `flutter pub get`
3. Start it in Chrome: `flutter run -d chrome`
4. Press `r` in the terminal to hot reload after a code change, and `R` to restart.

**Other targets**
- Android phone or emulator: `flutter devices`, then `flutter run -d <device id>`.
- iOS simulator (Mac only): `open -a Simulator`, then `flutter run`.
- A phone-sized window in Chrome: open DevTools (Cmd + Option + I) and turn on the device toolbar.

**Checks before you push**
- `flutter analyze` must show no errors (infos are fine).
- `flutter test` runs the content tests in `test/`.

**Build and deploy the web version**
1. `flutter build web --release` (the output goes to `build/web`).
2. Preview it: `cd build/web && python3 -m http.server 8765`, then open http://localhost:8765.
3. The draft is hosted on Vercel from `build/web`, with a `vercel.json` that sends every path to `index.html`.

## How the code is organised

- `lib/main.dart`: routes (go_router), light and dark themes, larger-text scaling.
- `lib/data/app_state.dart`: all app state (profile, XP, streak, levels, badges, quick-check results, settings).
- `lib/models/content.dart`: the content model (Roadmap, Slice, Node, Question).
- `lib/widgets/common.dart`: the colour palette (light and dark), the top stats bar, panels and the tutor bubble.
- `lib/screens/`: one file per screen.

**Screens**
1. `onboarding_screen.dart`: welcome, then age, goal, horizon, experience and confidence.
2. `signin_screen.dart`: sign-in with Google or an email link (demo only).
3. `placement_screen.dart`: the 5-question quick check, also used for the retest.
4. `shell.dart`: the bottom bar (Explore, Practice, Tutor, Progress, Profile).
5. `wheel_screen.dart`: the wheel of 13 investment types, or a list view.
6. `tree_screen.dart`: one slice's roadmap of missions.
7. `mission_screen.dart`: lesson cards, then questions with tutor feedback.
8. `result_screen.dart`: mission complete, confidence after, first real step.
9. `time_machine_screen.dart`: play-money replay with a crash moment.
10. `progress_screen.dart`, `tutor_screen.dart`, `profile_screen.dart`.

## Where the data comes from

- `assets/roadmap.json`: 13 slices, 52 missions, 92 questions, each with an explanation and source links.
- `assets/eu_benchmark.json`: the quick-check questions and the Poland and EU percentages, based on Eurobarometer 525 (2023).
- Both are copies of `backend/content/`. After editing a slice there, run `python3 backend/content/validate_content.py`, then copy `roadmap.json` and `eu_benchmark.json` into `frontend/assets/`.

## What is still demo or placeholder

- There is no backend connection yet. Scoring, XP and unlocks run inside the app, and a page refresh resets them.
- The tutor shows the stored explanation for each question. The live AI comes from the backend's `POST /tutor`.
- The time machine uses a sample curve, not real index data.
- Sign-in (Google and email) is a demo and stores nothing.
- The weekly league uses demo players, and the lesson cards have illustration and example placeholders.

## Next step: connect to the backend

- The backend serves its OpenAPI spec at `http://localhost:8001/openapi.json` when it runs locally.
- Plan: put an `ApiClient` between the screens and the data, with a local version (today's bundled JSON) and an HTTP version (the backend), so screens keep working while the backend grows.
- Dart models can be generated from the spec: `openapi-generator-cli generate -i http://localhost:8001/openapi.json -g dart-dio -o lib/api`.
