"""Local review window. Runs in a separate process so Tk owns its main thread."""

import json
import sys


def main():
    try:
        draft = json.load(sys.stdin)
        import tkinter as tk
        from tkinter.scrolledtext import ScrolledText

        root = tk.Tk()
        approved = [False]
        root.title("Webmail MCP — review before sending")
        root.geometry("820x650")
        tk.Label(root, text="Send this exact email from your mailbox?", font=("Arial", 14, "bold")).pack(pady=12)
        review = ScrolledText(root, wrap="word", font=("TkFixedFont", 11))
        review.pack(fill="both", expand=True, padx=16)
        preview = f"From: {draft['from']}\nTo: {', '.join(draft['to'])}\nCc: {', '.join(draft['cc'])}\nSubject: {draft['subject']}\n\n{draft['body']}"
        review.insert("1.0", preview)
        review.configure(state="disabled")
        bar = tk.Frame(root)
        bar.pack(pady=16)

        def confirm():
            approved[0] = True
            root.destroy()

        tk.Button(bar, text="Cancel — do not send", command=root.destroy, width=25).pack(side="left", padx=12)
        tk.Button(bar, text="Send this email", command=confirm, width=25).pack(side="left", padx=12)
        root.protocol("WM_DELETE_WINDOW", root.destroy)
        root.after(180000, root.destroy)
        root.mainloop()
        return 0 if approved[0] else 2
    except Exception:
        # No input content or traceback is emitted to the parent or the model.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
