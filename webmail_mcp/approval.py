"""Local review window. Runs in a separate process so Tk owns its main thread."""

import json
import sys
import unicodedata

from .settings import MailError


def validate_content(subject, body):
    for value, label, limit, allowed in ((subject, "subject", 500, ""), (body, "body", 30000, "\t\n")):
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise MailError(f"The {label} must contain 1–{limit} characters.")
        for char in value:
            if char not in allowed and unicodedata.category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"}:
                raise MailError(f"The {label} contains unsupported control or formatting character U+{ord(char):04X}.")


def build_review(root, draft):
    import tkinter as tk
    from tkinter.scrolledtext import ScrolledText

    approved = False
    root.title("Webmail MCP — review before sending")
    root.geometry("820x650")
    body = draft["body"]
    domain = draft["from"].rsplit("@", 1)[1].lower()
    tk.Label(
        root, text=f"Review the entire email • {body.count(chr(10)) + 1} body lines • {len(body)} body characters"
    ).pack(pady=8)
    external = sum(address.rsplit("@", 1)[1].lower() != domain for address in draft["to"] + draft["cc"])
    tk.Label(root, text=f"{external} recipient(s) outside @{domain} • Scroll to the end to enable Send.").pack()
    tk.Label(root, text="If your chat timed out, click Cancel.").pack()
    review = ScrolledText(root, wrap="word", font=("TkFixedFont", 11))
    review.pack(fill="both", expand=True, padx=16)
    review.tag_configure("external", foreground="#9a3300", background="#fff0d6")
    review.insert("end", f"From: {draft['from']}\n")
    for label in ("to", "cc"):
        review.insert("end", f"{label.title()}: ")
        for index, address in enumerate(draft[label]):
            if index:
                review.insert("end", ", ")
            if address.rsplit("@", 1)[1].lower() != domain:
                review.insert("end", address + " [external]", "external")
            else:
                review.insert("end", address)
        review.insert("end", "\n")
    review.insert("end", f"Subject: {draft['subject']}\n\n{body}")
    review.configure(state="disabled")
    bar = tk.Frame(root)
    bar.pack(pady=12)
    tk.Button(bar, text="Cancel — do not send", command=root.destroy).pack(side="left", padx=12)

    def at_end():
        return review.winfo_ismapped() and review.winfo_height() > 1 and review.yview()[1] >= 1.0

    def confirm():
        nonlocal approved
        if at_end():
            approved = True
            root.destroy()

    send = tk.Button(bar, text="Send this email", state="disabled", command=confirm)
    send.pack(side="left", padx=12)

    def update_scroll(first, last):
        review.vbar.set(first, last)
        send.configure(state="normal" if at_end() else "disabled")

    review.configure(yscrollcommand=update_scroll)
    root.after_idle(lambda: update_scroll(*review.yview()))
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.after(180000, root.destroy)
    root.mainloop()
    return approved


def main():
    try:
        draft = json.load(sys.stdin)
        validate_content(draft["subject"], draft["body"])
        import tkinter as tk

        return 0 if build_review(tk.Tk(), draft) else 2
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
