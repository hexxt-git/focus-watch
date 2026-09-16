# focus-watch (MacOS)

A small always-on-top window that shows which macOS app currently has focus, and
which one had it before that.

<img width="303" height="200" alt="2026-09-16_15-10-32" src="https://github.com/user-attachments/assets/412d0eda-db28-4f2e-8733-3398a12c4bed" />


Built to debug overlay apps, where the menu bar is useless as a focus indicator:
an app with `NSApplicationActivationPolicy.accessory` has no menu bar, so the
previous app's menus stay on screen even while the overlay holds the keyboard.
This reads `NSWorkspace.frontmostApplication` directly instead.

## Using a release

Download the `.dmg` for your architecture — `aarch64` for Apple Silicon,
`x64` for Intel — from [Releases][releases], or from the artifacts of any
[build run][runs].

Releases are unsigned, so macOS quarantines them on download:

```sh
xattr -dr com.apple.quarantine /Applications/focus-watch.app
```

[releases]: https://github.com/hexxt-git/focus-watch/releases
[runs]: https://github.com/hexxt-git/focus-watch/actions/workflows/build.yml

## Running from source

```sh
pnpm install   # just @tauri-apps/cli
pnpm dev       # or: cd src-tauri && cargo run
pnpm build     # .app + .dmg in src-tauri/target/release/bundle/
```

There is no frontend watcher, because there is no frontend build — edit
`ui/index.html` and reload the window.

CI builds both macOS architectures through the `build` workflow, triggered
manually (`gh workflow run build`) or by pushing a `v*` tag, which also drafts a
release. macOS runners bill at 10x, so it deliberately doesn't run per-commit.

There is no Windows or Linux build, by design. Windows has a straightforward
equivalent (`GetForegroundWindow`) and X11 has a workable one
(`_NET_ACTIVE_WINDOW`), but Wayland has none — a client cannot ask which window
holds focus, and that is its security model rather than a missing API. Building
for platforms where the window would sit at `—` is worse than not shipping them,
so `main.rs` fails to compile off macOS instead.

## How it works

- `src-tauri/src/main.rs` polls `NSWorkspace.frontmostApplication` every 150ms on
  the main thread and emits a `focus` event whenever the frontmost pid changes.
  Its own pid is skipped, so clicking this window neither reports itself as
  focused nor pushes the app you care about into "before that".
- `ui/index.html` is plain static HTML served via `frontendDist` — no bundler and
  no `@tauri-apps/api`, just `window.__TAURI__` through `withGlobalTauri`.
- The window joins all Spaces and sits over fullscreen apps
  (`NSWindowCollectionBehavior`), and runs as an accessory app so it stays out of
  the Dock and the app switcher. With no Dock tile, closing the window quits.

Reports the frontmost *application*, not the key window — it won't distinguish
which window within an app has the keyboard.
