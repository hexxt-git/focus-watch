# focus-watch

A small always-on-top window that shows which macOS app currently has focus, and
which one had it before that.

Built to debug overlay apps, where the menu bar is useless as a focus indicator:
an app with `NSApplicationActivationPolicy.accessory` has no menu bar, so the
previous app's menus stay on screen even while the overlay holds the keyboard.
This reads `NSWorkspace.frontmostApplication` directly instead.

## Running

```sh
pnpm install   # just @tauri-apps/cli
pnpm dev       # or: cd src-tauri && cargo run
pnpm build     # .app + .dmg in src-tauri/target/release/bundle/
```

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
