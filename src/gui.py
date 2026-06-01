from __future__ import annotations

from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .app_metadata import APP_NAME
from .converter import ConversionError, ConversionOptions, convert_djvu_to_pdf


class ConverterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("720x460")
        self.minsize(620, 380)

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.ddjvu_var = tk.StringVar()
        self.quality_var = tk.IntVar(value=90)
        self.dpi_var = tk.StringVar()
        self.keep_temp_var = tk.BooleanVar(value=False)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker: threading.Thread | None = None

        self._build_ui()
        self.after(100, self._poll_events)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(5, weight=1)

        frame = ttk.Frame(self, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)

        self._file_row(frame, 0, "Input DJVU", self.input_var, self._choose_input)
        self._file_row(frame, 1, "Output PDF", self.output_var, self._choose_output)
        self._file_row(frame, 2, "ddjvu path", self.ddjvu_var, self._choose_ddjvu)

        ttk.Label(frame, text="Quality").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Spinbox(frame, from_=1, to=100, textvariable=self.quality_var, width=8).grid(
            row=3, column=1, sticky="w", pady=(8, 0)
        )
        ttk.Label(frame, text="DPI").grid(row=3, column=1, sticky="w", padx=(100, 0), pady=(8, 0))
        ttk.Entry(frame, textvariable=self.dpi_var, width=8).grid(row=3, column=1, sticky="w", padx=(135, 0), pady=(8, 0))
        ttk.Checkbutton(frame, text="Keep temp", variable=self.keep_temp_var).grid(
            row=3, column=1, sticky="w", padx=(230, 0), pady=(8, 0)
        )

        self.progress = ttk.Progressbar(frame, mode="determinate")
        self.progress.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(12, 6))

        self.log = tk.Text(frame, height=12, wrap="word")
        self.log.grid(row=5, column=0, columnspan=3, sticky="nsew")
        frame.rowconfigure(5, weight=1)

        self.convert_button = ttk.Button(frame, text="Convert", command=self._start_conversion)
        self.convert_button.grid(row=6, column=2, sticky="e", pady=(10, 0))

    def _file_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        command: object,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4, padx=(8, 8))
        ttk.Button(parent, text="Browse", command=command).grid(row=row, column=2, sticky="e", pady=4)

    def _choose_input(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("DJVU files", "*.djvu *.djv"), ("All files", "*.*")])
        if path:
            self.input_var.set(path)
            if not self.output_var.get():
                self.output_var.set(str(Path(path).with_suffix(".pdf")))

    def _choose_output(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if path:
            self.output_var.set(path)

    def _choose_ddjvu(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("ddjvu executable", "ddjvu.exe ddjvu"), ("All files", "*.*")])
        if path:
            self.ddjvu_var.set(path)

    def _start_conversion(self) -> None:
        dpi = self.dpi_var.get().strip()
        try:
            options = ConversionOptions(
                quality=int(self.quality_var.get()),
                dpi=int(dpi) if dpi else None,
                keep_temp=self.keep_temp_var.get(),
                ddjvu_path=self.ddjvu_var.get().strip() or None,
            )
        except ValueError:
            messagebox.showerror("Conversion failed", "Quality and DPI must be valid numbers.")
            return

        self.convert_button.configure(state="disabled")
        self.progress.configure(value=0, maximum=100)
        self._append_log("Starting conversion...")
        self.worker = threading.Thread(
            target=self._run_conversion,
            args=(self.input_var.get(), self.output_var.get(), options),
            daemon=True,
        )
        self.worker.start()

    def _run_conversion(self, input_path: str, output_path: str, options: ConversionOptions) -> None:
        def progress(current: int, total: int, message: str) -> None:
            self.events.put(("progress", (current, total, message)))

        try:
            result = convert_djvu_to_pdf(input_path, output_path, options, progress=progress)
        except ConversionError as exc:
            self.events.put(("error", str(exc)))
        else:
            self.events.put(("success", str(result)))

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "progress":
                    current, total, message = payload  # type: ignore[misc]
                    if total:
                        self.progress.configure(maximum=total, value=current)
                    self._append_log(str(message))
                elif kind == "error":
                    self.convert_button.configure(state="normal")
                    self._append_log(f"Failed: {payload}")
                    messagebox.showerror("Conversion failed", str(payload))
                elif kind == "success":
                    self.convert_button.configure(state="normal")
                    self.progress.configure(value=self.progress["maximum"])
                    self._append_log(f"Done: {payload}")
                    messagebox.showinfo("Conversion complete", f"Saved PDF:\n{payload}")
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def _append_log(self, message: str) -> None:
        self.log.insert("end", f"{message}\n")
        self.log.see("end")


def main() -> None:
    app = ConverterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
