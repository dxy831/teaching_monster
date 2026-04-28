base_class = """
class TeachingScene(Scene):
    # Right-side safe area boundary constants
    RIGHT_X_MIN = 0.3
    RIGHT_X_MAX = 6.5
    RIGHT_Y_MIN = -3.5
    RIGHT_Y_MAX = 3.0
    RIGHT_CENTER = np.array([3.4, -0.25, 0])
    RIGHT_MAX_WIDTH = 6.0
    RIGHT_MAX_HEIGHT = 5.5

    def _build_lecture_group(self, lecture_lines):
        lecture_texts = [Text(line, font_size=20, color="#2C1608") for line in lecture_lines]
        lecture_group = VGroup(*lecture_texts).arrange(DOWN, aligned_edge=LEFT, buff=0.3)
        return lecture_group

    def setup_layout(self, title_text, lecture_lines, lecture_line_indices=None):
        # BASE - warm color scheme
        self.camera.background_color = "#FFFDF4"  # warm ivory background

        # Main title - must use bold weight="BOLD", color #BE8944
        self.title = Text(title_text, font_size=28, color="#BE8944", weight="BOLD").to_edge(UP)
        self.add(self.title)

        # Left-side lecture content (bullets with "-")
        # ⚠️ Lecture text starts from the top-left corner; Y-axis centering is forbidden
        self.lecture = self._build_lecture_group(lecture_lines)
        self.lecture.next_to(self.title, DOWN, buff=1.0).to_edge(LEFT, buff=0.3)
        self.add(self.lecture)
        self.lecture_anchor = self.lecture.get_corner(UL)
        self.current_lecture_line_indices = list(lecture_line_indices) if lecture_line_indices is not None else list(range(len(lecture_lines)))

        # Define fine-grained animation grid (6x6 grid on right side)
        self.grid = {}
        rows = ["A", "B", "C", "D", "E", "F"]  # Top to bottom
        cols = ["1", "2", "3", "4", "5", "6"]  # Left to right

        for i, row in enumerate(rows):
            for j, col in enumerate(cols):
                x = 0.5 + j * 1
                y = 2.2 - i * 1
                self.grid[f"{row}{col}"] = np.array([x, y, 0])

    def create_code_block(self, code_text, language="python"):
        \"\"\"
        Create a standardized light-background code block.
        Copy the following code exactly; do not modify any parameters, otherwise the style will become inconsistent!!!
        Must use the tango formatter style, the background color must use the light gold palette, and it must have a border.
        
        Args:
            code_text: code text string
            language: programming language, default python
        
        Returns:
            Code object
        \"\"\"
        return Code(
            code_string=code_text,  # use code_string instead of code
            language=language,
            background="rectangle",  # 🔴 must have
            formatter_style="tango",  # 🔴 must be tango, no other value allowed
            background_config={  # 🔴 must have, and must use this palette
                "fill_color": "#fff7e8",   # light gold background
                "stroke_color": "#e4c8a6", # gold border
                "stroke_width": 2
            }
        )

    def place_at_grid(self, mobject, grid_pos, scale_factor=1.0):
        \"\"\"Place an object at the grid position.\"\"\"
        mobject.scale(scale_factor)
        mobject.move_to(self.grid[grid_pos])
        return mobject

    def highlight_lecture_line(self, index, color):
        \"\"\"
        Highlight the currently spoken lecture line by changing its color, used for "which line is being spoken".
        
        Args:
            index: index of the lecture line (0-based)
            color: highlight color, can be chosen freely from any semantic palette color
        
        Returns:
            Animation object that can be passed to self.play()
        
        Usage examples:
            self.play(self.highlight_lecture_line(0, "#C35101"))   # line 1 becomes emphasized orange
            self.play(self.highlight_lecture_line(0, "#478211"))   # line 1 becomes green
            self.play(self.highlight_lecture_line(1, "#1A7F99"))   # line 2 becomes blue
        \"\"\"
        if 0 <= index < len(self.lecture):
            return self.lecture[index].animate.set_color(color)
        return Wait(0)

    def unhighlight_lecture_line(self, index, color="#2C1608"):
        \"\"\"
        Remove highlighting and restore the lecture line to its original color.
        
        Args:
            index: index of the lecture line (0-based)
            color: restore color, default dark brown #2C1608 (original text color)
        
        Returns:
            Animation object that can be passed to self.play()
        
        Usage examples:
            self.play(self.unhighlight_lecture_line(0))  # restore line 1 to original color
        \"\"\"
        if 0 <= index < len(self.lecture):
            return self.lecture[index].animate.set_color(color)
        return Wait(0)

    def speak_and_highlight(self, index, color, wait_time=1.5):
        \"\"\"
        Highlight a lecture line while speaking it, wait briefly, then automatically restore the original color.
        Completes the full flow "highlight → wait → restore" in one step.
        
        Args:
            index: index of the lecture line (0-based)
            color: highlight color, can be chosen freely from any semantic palette color
            wait_time: duration of the highlight in seconds, default 1.5 seconds
        
        Usage examples:
            self.speak_and_highlight(0, "#C35101")              # highlight line 1 in orange for 1.5 seconds then restore
            self.speak_and_highlight(1, "#478211", wait_time=2)  # highlight line 2 in green for 2 seconds then restore
            self.speak_and_highlight(2, "#1A7F99")              # highlight line 3 in blue
        \"\"\"
        if 0 <= index < len(self.lecture):
            self.play(self.lecture[index].animate.set_color(color))
            self.wait(wait_time)
            self.play(self.lecture[index].animate.set_color("#2C1608"))

    def play_synced_step(
        self,
        line_indices,
        audio_path,
        audio_duration,
        *animations,
        highlight_color="#C35101",
        reset_color="#2C1608",
    ):
        \"\"\"
        V5.0 core synchronization primitive:
        - use add_sound to play audio
        - keep the corresponding left-side short text highlighted for the entire audio duration
        - allow right-side animation to run in parallel with the audio

        Args:
            line_indices: index or indices of the currently displayed left-side lecture lines
            audio_path: absolute path to the audio file
            audio_duration: actual physical duration of the audio in seconds
            *animations: animations to run in parallel with the audio
            highlight_color: highlight color
            reset_color: restore color
        \"\"\"
        if isinstance(line_indices, int):
            line_indices = [line_indices]
        elif isinstance(line_indices, tuple):
            line_indices = list(line_indices)
        elif not isinstance(line_indices, list):
            raise TypeError("line_indices must be an int or a list of ints")

        if not line_indices:
            raise ValueError("line_indices must not be empty")
        if audio_duration is None or not isinstance(audio_duration, (int, float)):
            raise ValueError(f"audio_duration must be a positive number, got {audio_duration!r}")
        if audio_duration <= 0:
            raise ValueError(f"audio_duration must be positive, got {audio_duration}")

        current_line_indices = getattr(self, "current_lecture_line_indices", list(range(len(self.lecture))))
        displayed_indices = []
        for line_index in line_indices:
            if not isinstance(line_index, int):
                raise TypeError("line_indices must contain only ints")
            
            # Find ALL display indices that correspond to this absolute line_index
            matches = [i for i, val in enumerate(current_line_indices) if val == line_index]
            if not matches:
                raise IndexError(f"Lecture line index {line_index} is not currently displayed")
                
            for display_index in matches:
                if display_index not in displayed_indices:
                    displayed_indices.append(display_index)

        for display_index in displayed_indices:
            self.lecture[display_index].set_color(highlight_color)
        self.add_sound(audio_path)

        if animations:
            self.play(*animations, run_time=audio_duration)
        else:
            self.wait(audio_duration)

        for display_index in displayed_indices:
            self.lecture[display_index].set_color(reset_color)

    def replace_lecture_lines(self, lecture_lines, lecture_line_indices=None):
        \"\"\"
        Replace the left-side lecture text with a new batch while keeping the top-left anchor fixed.
        Used for showing many steps in separate batches.
        \"\"\"
        new_lecture = self._build_lecture_group(lecture_lines)
        new_lecture.align_to(self.lecture_anchor, UL)
        self.play(FadeOut(self.lecture), FadeIn(new_lecture))
        self.remove(self.lecture)
        self.lecture = new_lecture
        self.current_lecture_line_indices = list(lecture_line_indices) if lecture_line_indices is not None else list(range(len(lecture_lines)))

    def place_in_area(self, mobject, top_left, bottom_right, scale_factor=1.0):
        \"\"\"Place an object at the center of a grid area and automatically crop to bounds.\"\"\"
        tl_pos = self.grid[top_left]
        br_pos = self.grid[bottom_right]
        
        # Calculate center of the area
        center_x = (tl_pos[0] + br_pos[0]) / 2
        center_y = (tl_pos[1] + br_pos[1]) / 2
        center = np.array([center_x, center_y, 0])
        
        mobject.scale(scale_factor)
        mobject.move_to(center)
        return mobject
"""
