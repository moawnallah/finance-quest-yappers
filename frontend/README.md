# frontend

The Flutter app for Finance Quest: one Dart codebase for web, Android, iOS and desktop. Owner: Michał.

Live: https://crococash.xyz

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
3. Production: build with `--no-tree-shake-icons --dart-define=API_URL=https://crococash.xyz/api`, run `tool/stamp_web.sh build/web` (so Cloudflare serves the new files), then copy `build/web` to `/opt/crococash/web` on the server (Caddy behind Cloudflare Tunnel).

## How the code is organised

- `lib/main.dart`: routes (go_router), light and dark themes, larger-text scaling.
- `lib/data/api.dart`: the backend client (accounts, guests, path, skills, tasks, tutor, leagues, admin). The backend URL is set at build time with `--dart-define=API_URL=...` (default `http://localhost:8001`).
- `lib/data/app_state.dart`: app state (profile, account, Emeralds, streak, settings, tutor conversations).
- `lib/models/content.dart`: the content model (Roadmap, Slice, Node, Question).
- `lib/widgets/`: `common.dart` (palette, stats bar, panels, tutor bubble) and `block_editor.dart` (drag-and-drop blocks).
- `lib/screens/`: one file per screen.

**Screens**
1. `onboarding_screen.dart`: welcome, email and password account (or guest), then the starting survey.
2. `signin_screen.dart`: the Google sign-in demo.
3. `placement_screen.dart`: the 5-question quick check, also used for the retest.
4. `shell.dart`: the bottom bar (Explore, Path, League, Progress) and the tutor button.
5. `wheel_screen.dart`: Explore, the wheel of skills-tree panels with each panel's roadmap.
6. `path_screen.dart`: the personal path from the backend router, and the "coming later" screen.
7. `skills_screen.dart`, `skill_screen.dart`: the skills-tree nodes and one node (cards and ways in).
8. `task_screen.dart`: easy items and medium day-X tasks; `hard_task_screen.dart`: hard tasks (plan as code, public and hidden tests); `drawn_test.dart`: quick checks and prerequisite checks; `steps_screen.dart`: the drag-and-drop plan question.
9. `league_screen.dart`, `progress_screen.dart`, `tutor_screen.dart`, `time_machine_screen.dart`, `admin_screen.dart`.

## Where the data comes from

- Skills, tasks, the path, leagues and the tutor come from the backend (`backend/`).
- `assets/roadmap.json`: 13 slices, 52 product topics, 92 questions, each with an explanation and source links.
- `assets/eu_benchmark.json`: the quick-check questions and the Poland and EU percentages, based on Eurobarometer 525 (2023).
- Both are copies of `backend/content/`. After editing a slice there, run `python3 backend/content/validate_content.py`, then copy `roadmap.json` and `eu_benchmark.json` into `frontend/assets/`.
- `assets/steps.json`: drafts for the drag-and-drop plan question, scored in the app.

## What is still demo or placeholder

- Google sign-in is a demo; email and password accounts are real.
- The time machine uses a sample curve, not real index data.
- The drag-and-drop plan question (`steps_screen.dart`) is scored in the app, not by the backend.
