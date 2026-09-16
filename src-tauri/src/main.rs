//! focus-watch is macOS only. The whole app is a thin wrapper around
//! `NSWorkspace.frontmostApplication`; Windows has an equivalent, X11 has a
//! workable one, and Wayland deliberately has none, so rather than ship windows
//! that permanently read "—", other platforms don't build at all.
#[cfg(not(target_os = "macos"))]
compile_error!("focus-watch is macOS only: it reads NSWorkspace.frontmostApplication");

use std::sync::Mutex;
use std::{thread, time::Duration};

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager};

const POLL: Duration = Duration::from_millis(150);

/// What the readout shows. `previous` is whatever held focus before `current`.
#[derive(Clone, Default, Serialize)]
struct Focus {
    current: String,
    previous: String,
    /// Kept only to spot a change without comparing names, since two apps can
    /// share a display name.
    #[serde(skip)]
    pid: i32,
}

static STATE: Mutex<Focus> = Mutex::new(Focus {
    current: String::new(),
    previous: String::new(),
    pid: 0,
});

fn frontmost() -> Option<(i32, String)> {
    use objc2::runtime::AnyObject;
    use objc2::{class, msg_send};
    use std::ffi::{c_char, CStr};

    unsafe {
        let workspace: *mut AnyObject = msg_send![class!(NSWorkspace), sharedWorkspace];
        let app: *mut AnyObject = msg_send![workspace, frontmostApplication];
        if app.is_null() {
            return None;
        }
        let pid: i32 = msg_send![app, processIdentifier];
        let name: *mut AnyObject = msg_send![app, localizedName];
        if name.is_null() {
            return Some((pid, format!("pid {pid}")));
        }
        let utf8: *const c_char = msg_send![name, UTF8String];
        if utf8.is_null() {
            return Some((pid, format!("pid {pid}")));
        }
        Some((pid, CStr::from_ptr(utf8).to_string_lossy().into_owned()))
    }
}

/// `NSWorkspace` wants the main thread, so every tick hops there.
fn tick(app: &AppHandle) {
    let Some((pid, name)) = frontmost() else {
        return;
    };
    // Ignore ourselves: clicking the readout shouldn't make the readout the
    // answer, and it must not push the app you care about into `previous`.
    if pid == std::process::id() as i32 {
        return;
    }

    let mut state = STATE.lock().unwrap();
    if state.pid == pid {
        return;
    }
    if !state.current.is_empty() {
        state.previous = state.current.clone();
    }
    state.current = name;
    state.pid = pid;
    let snapshot = state.clone();
    drop(state);

    let _ = app.emit("focus", snapshot);
}

#[tauri::command]
fn focus_state() -> Focus {
    STATE.lock().unwrap().clone()
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![focus_state])
        // No Dock tile, so closing the window is the only way out.
        .on_window_event(|window, event| {
            if matches!(event, tauri::WindowEvent::Destroyed) {
                window.app_handle().exit(0);
            }
        })
        .setup(|app| {
            // Accessory: no Dock tile and no app-switcher entry, so the readout
            // never becomes the thing being measured.
            app.set_activation_policy(tauri::ActivationPolicy::Accessory);

            // Ride along to every Space instead of living on the one it was
            // opened in: join all Spaces, sit over fullscreen apps, stay out of
            // Mission Control and out of Cmd-` cycling.
            if let Some(w) = app.get_webview_window("main") {
                unsafe {
                    let ns = w.ns_window()? as *mut objc2::runtime::AnyObject;
                    let behavior: usize = (1 << 0) | (1 << 3) | (1 << 6) | (1 << 8);
                    let _: () = objc2::msg_send![&*ns, setCollectionBehavior: behavior];
                }
            }

            let handle = app.handle().clone();
            thread::spawn(move || loop {
                thread::sleep(POLL);
                let h = handle.clone();
                let _ = handle.run_on_main_thread(move || tick(&h));
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
