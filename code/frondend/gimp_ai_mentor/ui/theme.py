"""深色主题 CSS。颜色取自原型 HTML。"""

from __future__ import annotations

CSS = """
window, .ai-panel-bg {
    background-color: #2c2c2c;
    color: #d1d1d1;
    font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
}

.panel-header {
    background-color: rgba(38, 38, 38, 0.7);
    border-bottom: 1px solid #444444;
    padding: 8px 12px;
}

.panel-header label {
    font-weight: bold;
    color: #fb923c;
}

.section-label {
    color: #a3a3a3;
    font-size: 10px;
    font-weight: bold;
    /* GTK 不支持 letter-spacing；用 small caps 退而求其次 */
}

.btn-primary {
    background-image: none;
    background-color: #ea580c;
    color: #ffffff;
    border-radius: 4px;
    padding: 6px 12px;
    border: none;
    font-weight: 500;
}
.btn-primary:hover { background-color: #c2410c; }
.btn-primary:disabled { background-color: #6b3410; color: #cccccc; }

.btn-ghost {
    background-image: none;
    background-color: rgba(0, 0, 0, 0);
    color: #d1d1d1;
    border-radius: 4px;
    padding: 4px 8px;
    border: 1px solid #444;
}
.btn-ghost:hover { background-color: #404040; }

.btn-danger {
    background-image: none;
    background-color: #404040;
    color: #ef4444;
    border-radius: 4px;
    padding: 4px 8px;
    border: 1px solid #5a1f1f;
}
.btn-danger:hover { background-color: #5a1f1f; color: #ffffff; }

.input-area {
    background-color: #171717;
    color: #d1d1d1;
    border: 1px solid #444444;
    border-radius: 4px;
    padding: 8px;
}

.diagnosis-card {
    background-color: rgba(0, 0, 0, 0.2);
    border: 1px solid #404040;
    border-radius: 8px;
    padding: 10px;
}

.diagnosis-summary {
    background-color: rgba(64, 64, 64, 0.3);
    color: #d1d1d1;
    padding: 8px;
    border-radius: 4px;
    font-size: 11px;
}

.score-badge {
    color: #4ade80;
    font-weight: bold;
}

.step-row {
    background-color: #262626;
    border-left: 2px solid #444;
    padding: 8px;
    border-radius: 4px;
}
.step-row:hover { background-color: #303030; }

.step-row.step-pending { border-left-color: #737373; }
.step-row.step-active  { border-left-color: #f97316; background-color: #303030; }
.step-row.step-completed { border-left-color: #22c55e; }
.step-row.step-ignored { border-left-color: #525252; }
.step-row.step-ignored label { color: #737373; }

.step-number {
    background-color: rgba(249, 115, 22, 0.2);
    color: #f97316;
    border-radius: 999px;
    padding: 2px 6px;
    font-weight: bold;
    font-size: 10px;
}

.step-title { color: #ffffff; font-size: 12px; font-weight: 500; }
.step-desc  { color: #737373; font-size: 10px; }

.toast {
    border-radius: 4px;
    padding: 8px 12px;
    color: #ffffff;
    font-size: 12px;
}
.toast-info    { background-color: #2563eb; }
.toast-success { background-color: #16a34a; }
.toast-warning { background-color: #ca8a04; color: #1a1a1a; }
.toast-error   { background-color: #dc2626; }

.footer-bar {
    background-color: rgba(38, 38, 38, 0.8);
    color: #a3a3a3;
    padding: 4px 8px;
    font-size: 10px;
    border-top: 1px solid #444;
}

.empty-hint {
    color: #737373;
    font-size: 11px;
}
"""


def apply_theme() -> None:
    """安装全局 CSS。多次调用幂等。"""
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gdk, Gtk
    except (ImportError, ValueError):
        return

    provider = Gtk.CssProvider()
    provider.load_from_data(CSS.encode("utf-8"))
    screen = Gdk.Screen.get_default()
    if screen is not None:
        Gtk.StyleContext.add_provider_for_screen(
            screen,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
