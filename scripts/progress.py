"""Progress bar display for terminal output."""


def format_time(seconds: float) -> str:
    """Format seconds into human-readable time."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


class ProgressBar:
    """
    Terminal progress bar with match display.

    Displays a progress bar with stats and recent keyword matches below it.
    Handles ANSI cursor manipulation for clean multi-line updates.
    """

    # ANSI escape codes
    CLEAR_LINE = "\033[K"
    MOVE_UP = "\033[A"

    def __init__(self, total: int, width: int = 30, workers: int = 1):
        self.total = total
        self.width = width
        self.workers = workers
        self.current = 0
        self.matches = 0
        self.recent_matches: list[tuple[str, str, str]] = []
        self._prev_match_lines = 0

    def update(
        self,
        current: int,
        filename: str,
        elapsed: float,
        matches: int,
        new_matches: list[tuple[str, str, str]] | None = None
    ) -> None:
        """
        Update and redraw the progress bar.

        Args:
            current: Number of items processed
            filename: Current file being processed
            elapsed: Time elapsed in seconds
            matches: Total match count
            new_matches: New (keyword, context, filename) tuples to display
        """
        self.current = current
        self.matches = matches

        if new_matches:
            self.recent_matches.extend(new_matches)
            # Keep only the last 10
            if len(self.recent_matches) > 10:
                self.recent_matches = self.recent_matches[-10:]

        self._render(filename, elapsed)

    def _render(self, filename: str, elapsed: float) -> None:
        """Render the progress bar to terminal."""
        percent = self.current / self.total if self.total > 0 else 0
        filled = int(self.width * percent)
        bar = "█" * filled + "░" * (self.width - filled)

        # Calculate speed and ETA
        speed = self.current / elapsed if elapsed > 0 else 0
        remaining = self.total - self.current
        eta = remaining / speed if speed > 0 else 0

        # Truncate filename if too long
        display_name = filename[:20] + "..." if len(filename) > 20 else filename

        # Move cursor up to overwrite previous match lines
        if self._prev_match_lines > 0:
            print(self.MOVE_UP * self._prev_match_lines, end="")

        # Build progress line
        line = (
            f"\r  [{bar}] {self.current}/{self.total} ({percent*100:.0f}%) | "
            f"{speed:.1f} files/sec | "
            f"ETA: {format_time(eta)} | "
            f"Matches: {self.matches} | "
            f"Workers: {self.workers} | "
            f"{display_name:<23}{self.CLEAR_LINE}"
        )

        # Add recent matches
        match_lines = 0
        if self.recent_matches:
            display_matches = self.recent_matches[-3:]
            match_lines = len(display_matches)
            for keyword, context, match_file in display_matches:
                ctx = context[:60] + "..." if len(context) > 60 else context
                fname = match_file[:15] + "..." if len(match_file) > 15 else match_file
                line += f"\n    → [{keyword}] in {fname}: \"{ctx}\"{self.CLEAR_LINE}"

        # Clear extra lines from previous render
        extra = self._prev_match_lines - match_lines
        if extra > 0:
            line += (f"\n{self.CLEAR_LINE}" * extra) + (self.MOVE_UP * extra)

        print(line, end="", flush=True)
        self._prev_match_lines = match_lines

    def finish(self) -> None:
        """Complete the progress bar and move past match lines."""
        if self._prev_match_lines > 0:
            print("\n" * self._prev_match_lines, end="")
        print()
