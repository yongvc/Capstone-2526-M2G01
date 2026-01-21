"""
Embedded OpenCV display for Tkinter.
Uses win32gui to reparent OpenCV window as child of Tkinter frame.
Provides native OpenCV rendering performance in a single-window UI.
"""

import cv2
import numpy as np
import win32gui
import win32con


class EmbeddedCVDisplay:
    """
    Embeds an OpenCV window inside a Tkinter frame using Windows API.

    This provides native OpenCV rendering performance (cv2.imshow) while
    maintaining a single-window appearance with the Tkinter UI.
    """

    def __init__(self, parent_frame, window_name="Camera"):
        """
        Initialize embedded display.

        Args:
            parent_frame: Tkinter frame widget to embed into
            window_name: Name for the OpenCV window
        """
        self.parent_frame = parent_frame
        self.window_name = window_name
        self.cv_hwnd = None
        self.embedded = False
        self._last_size = (0, 0)
        self._creation_attempts = 0
        self._max_attempts = 30  # More attempts since we wait for Tkinter
        self._first_frame_shown = False

    def _create_and_embed(self):
        """Create OpenCV window and embed into Tkinter frame."""
        if self._creation_attempts >= self._max_attempts:
            print(
                f"EmbeddedCVDisplay: Failed to embed after {self._max_attempts} attempts, using fallback"
            )
            return False

        self._creation_attempts += 1

        try:
            # Force Tkinter to update and realize the frame
            self.parent_frame.update_idletasks()
            self.parent_frame.update()

            # Check if the frame has valid dimensions yet
            w = self.parent_frame.winfo_width()
            h = self.parent_frame.winfo_height()

            if w <= 1 or h <= 1:
                # Frame not yet realized, try again later
                print(
                    f"EmbeddedCVDisplay: Frame not ready (size={w}x{h}), attempt {self._creation_attempts}"
                )
                return False

            # Get Tkinter frame handle FIRST (before creating OpenCV window)
            tk_hwnd = self.parent_frame.winfo_id()
            if tk_hwnd == 0:
                print("EmbeddedCVDisplay: Could not get Tkinter frame handle")
                return False

            print(
                f"EmbeddedCVDisplay: Tkinter frame handle = {tk_hwnd}, size = {w}x{h}"
            )

            # Create OpenCV window
            cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(self.window_name, w, h)

            # Show a blank frame to ensure window is created
            blank = np.zeros((h, w, 3), dtype=np.uint8)
            cv2.imshow(self.window_name, blank)
            cv2.waitKey(1)

            # Find OpenCV window handle - try multiple times
            for attempt in range(10):
                self.cv_hwnd = win32gui.FindWindow(None, self.window_name)
                if self.cv_hwnd != 0:
                    break
                cv2.waitKey(10)

            if self.cv_hwnd == 0:
                print("EmbeddedCVDisplay: Could not find OpenCV window handle")
                return False

            print(f"EmbeddedCVDisplay: OpenCV window handle = {self.cv_hwnd}")

            # Remove window decorations (title bar, borders, etc.)
            style = win32gui.GetWindowLong(self.cv_hwnd, win32con.GWL_STYLE)
            style = style & ~win32con.WS_CAPTION
            style = style & ~win32con.WS_THICKFRAME
            style = style & ~win32con.WS_MINIMIZEBOX
            style = style & ~win32con.WS_MAXIMIZEBOX
            style = style & ~win32con.WS_SYSMENU
            style = style | win32con.WS_CHILD  # Make it a child window
            win32gui.SetWindowLong(self.cv_hwnd, win32con.GWL_STYLE, style)

            # Reparent OpenCV window to Tkinter frame
            win32gui.SetParent(self.cv_hwnd, tk_hwnd)

            # Position and resize to fill container
            win32gui.MoveWindow(self.cv_hwnd, 0, 0, w, h, True)
            self._last_size = (w, h)

            # Force redraw
            win32gui.ShowWindow(self.cv_hwnd, win32con.SW_SHOW)
            win32gui.UpdateWindow(self.cv_hwnd)

            self.embedded = True
            print(f"EmbeddedCVDisplay: Successfully embedded OpenCV window ({w}x{h})")
            return True

        except Exception as e:
            print(f"EmbeddedCVDisplay: Error during embedding: {e}")
            import traceback

            traceback.print_exc()
            return False

    def update(self, frame):
        """
        Display frame in embedded window.

        Args:
            frame: OpenCV BGR frame to display
        """
        if frame is None:
            return

        # Create and embed on first frame
        if not self.embedded:
            if not self._create_and_embed():
                # Fallback: show in separate window if embedding not ready
                if not self._first_frame_shown:
                    cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
                    self._first_frame_shown = True
                cv2.imshow(self.window_name, frame)
                cv2.waitKey(1)
                return

        # Resize OpenCV window to match container size
        w = self.parent_frame.winfo_width()
        h = self.parent_frame.winfo_height()

        if (w, h) != self._last_size and w > 10 and h > 10:
            self._last_size = (w, h)
            if self.cv_hwnd:
                try:
                    win32gui.MoveWindow(self.cv_hwnd, 0, 0, w, h, True)
                except Exception as e:
                    print(f"EmbeddedCVDisplay: Error resizing: {e}")

        # Display frame using native OpenCV rendering (FAST!)
        cv2.imshow(self.window_name, frame)
        cv2.waitKey(1)

    def destroy(self):
        """Cleanup OpenCV window."""
        try:
            cv2.destroyWindow(self.window_name)
        except Exception:
            pass
        self.embedded = False
        self.cv_hwnd = None
