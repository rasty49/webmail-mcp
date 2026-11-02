"""Exercise the actual Tk widgets under a display (CI uses Xvfb)."""

import tkinter as tk
from tkinter.scrolledtext import ScrolledText

from webmail_mcp.approval import build_review


def widgets(parent):
    for child in parent.winfo_children():
        yield child
        yield from widgets(child)


def check_window(body, long):
    root = tk.Tk()
    errors = []

    def exercise():
        try:
            controls = list(widgets(root))
            send = next(w for w in controls if isinstance(w, tk.Button) and w["text"] == "Send this email")
            review = next(w for w in controls if isinstance(w, ScrolledText))
            assert "[external]" in review.get("1.0", "end")
            assert len(review.tag_ranges("external")) == 2
            if long:
                assert str(send["state"]) == "disabled"
                send.invoke()
                review.yview_moveto(1.0)
                root.update_idletasks()
            assert str(send["state"]) == "normal"
            send.invoke()
        except BaseException as exc:
            errors.append(exc)
            root.destroy()

    root.after(200, exercise)
    draft = {
        "from": "me@example.org",
        "to": ["a@EXAMPLE.ORG", "b@external.test"],
        "cc": [],
        "subject": "Review",
        "body": body,
    }
    approved = build_review(root, draft)
    if errors:
        raise errors[0]
    assert approved


if __name__ == "__main__":
    check_window("Short body", False)
    check_window("First line\n" + "\n" * 400 + "Last line", True)
