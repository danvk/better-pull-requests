/**
 * github records comments on positions in a diff_hunk
 * This is really awkward and we prefer line numbers.
 * @param {string} diffHunk
 * @param {number} position
 * @return {{lineNumber: number, onLeft: boolean}}
 */
function parseDiffPosition(diffHunk, position) {
  var diffHunkLines = diffHunk.split('\n');
  var diffHeader = diffHunkLines.shift();
  var m = /^@@ -([0-9]+),[0-9]+ \+([0-9]+),[0-9]+ @@/.exec(diffHeader);
  if (!m) {
    console.warn("Couldn't parse diff header", diffHeader);
    return null;
  }

  var leftLineNumber = parseInt(m[1], 10) - 1;
  var rightLineNumber = parseInt(m[2], 10) - 1;
  var line;
  // comment.original_position = line number in the unified diff.
  // sometimes it's way larger than the number of lines in the diff.
  // In these cases, github shows it at the end of the diff.
  // We mirror this behavior.
  for (var i = 0; i < Math.min(position, diffHunkLines.length); i++) {
    line = diffHunkLines[i];
    var sign = line.substr(0, 1);
    if (sign == '-') {
      leftLineNumber++;
    } else if (sign == '+') {
      rightLineNumber++;
    } else {
      leftLineNumber++;
      rightLineNumber++;
    }
  }

  var onLeft = (line.substr(0, 1) == '-');
  return {
    lineNumber: onLeft ? leftLineNumber : rightLineNumber,
    onLeft: onLeft
  };
}
