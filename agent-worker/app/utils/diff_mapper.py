import re
import structlog
from dataclasses import dataclass
from typing import Optional

logger = structlog.get_logger()

HUNK_HEADER_RE = re.compile(
    r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@'

)

@dataclass
class PositionMap:
    """
    Maps new file line numbers to GitHub diff positions for one file.
    Only lines present in the new file (added + context) have positions.
    Removed lines have no position in the new file.
    """
    file_path: str
    positions: dict[int,int]

    def get_position(self, line_number: int) -> Optional[int]:
        return self.positions.get(line_number)
    
    def has_line(self, line_number: int) -> bool:
        return line_number in self.positions
    
def build_position_map(file_path: str, patch: str) -> PositionMap:
    """
    Parses a unified diff patch and builds a mapping from
    new file line numbers to GitHub diff positions.

    GitHub diff positions:
    - Start at 1 for the first line of the patch
    - Include hunk headers in the count
    - Continue sequentially across multiple hunks
    - Are file-specific (reset for each file)

    This mapping is required to post inline comments — GitHub
    rejects comments with invalid positions with HTTP 422.
    """
    positions: dict[int,int] = {}
    diff_position = 0
    current_new_line = 0

    if not patch:
        return PositionMap(file_path=file_path, positions={})
    
    for line in patch.split("\n"):
        if line.startswith("@@"):

            diff_position +=1
            match = HUNK_HEADER_RE.match(line)
            if match:
                 current_new_line = int(match.group(3))
        
        elif line.startswith("-"):

            diff_position +=1
        
        elif line.startswith("+"):

            positions[current_new_line] = diff_position
            diff_position +=1
            current_new_line +=1
        
        elif line.startswith("\\"):

            pass

        else:

            positions[current_new_line] = diff_position
            diff_position += 1
            current_new_line += 1

    logger.debug(
        "position_map_built",
        file_path=file_path,
        mappable_lines = len(positions),
        total_diff_positions=diff_position
    )

    return PositionMap(file_path=file_path, positions=positions)
    
def build_position_maps(
    files: list
) -> dict[str, PositionMap]:
    """
    Builds position maps for all files in a PR.
    Returns dict keyed by file path.

    Called once when the worker picks up a job —
    maps are passed to the agent so it never needs
    to think about diff positions.
    """
    maps = {}
    for diff_file in files:
        if diff_file.patch:
            maps[diff_file.filename] = build_position_map(
                diff_file.filename,
                diff_file.patch
            )
        else:
            # Binary files or files too large for diff
            maps[diff_file.filename] = PositionMap(
                file_path=diff_file.filename,
                positions={}
            )
    return maps
