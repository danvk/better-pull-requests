/**
 * github records comments on positions in a diff_hunk
 * This is really awkward and we prefer line numbers.
 * @param {string} diffHunk
 * @param {number} positionInDiffHunk
 * @return {{lineNumber: number, onLeft: boolean}}
 */
function parseDiffPosition(diffHunk, positionInDiffHunk) {
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

  for (var i = 0; i < Math.min(positionInDiffHunk, diffHunkLines.length); i++) {
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

/**
 * @template<T>
 * @param {Object.<T>} obj Object to filter.
 * @param {function(string, T):boolean}} fn Filter function, applied to each
 *     key/value pair in the object.
 * @return {Object.<T>} The filtered object.
 */
function filterObject(obj, fn) {
  var ret = {};
  for (var k in obj) {
    if (fn(k, obj[k])) {
      ret[k] = obj[k]
    }
  }
  return ret;
}

/**
 * This is like Python's itertools.groupBy, not underscorejs's _.groupBy
 * It groups _consecutive_ array elements which map to the same value, rather
 * than all elements which map to the same value.
 * @param {Array.<T>} arr The array.
 * @param {function(T)} fn Function mapping array elements to the key by
 *     which they should be grouped.
 * @retrn {Array.<Array.<T>>} The grouped array.
 */
function groupConsecutive(arr, fn) {
  var groups = [];
  var current, last;
  for (var i = 0; i < arr.length; i++) {
    var val = fn(arr[i]);
    if (i == 0 || val != last) {
      if (current) groups.push(current);
      current = [arr[i]];
      last = val;
    } else {
      current.push(arr[i]);
    }
  }
  if (current) groups.push(current);
  return groups;
}


/**
 * This rewrites the contents of an Element to hide quoted text.
 * It change '> So and so wrote:' to '<a href>...</a>'
 * @param {!Element} el Element to rewrite.
 */
function collapseQuotes(el) {
  var lines = $(el).html().split('\n');
  var isQuoted = function(line) { return line.substr(0, 4) == '&gt;' };
  var groupedLines = groupConsecutive(lines, isQuoted);

  var result = [];
  groupedLines.forEach(function(group) {
    var is_quoted = (group[0].substr(0, 4) == '&gt;');
    if (is_quoted) {
      var $link = $('<a class=collapsed-ellipsis href=#>&hellip;</a>')
          .data('contents', group.join('\n'));
      result.push($link);
    } else {
      result.push(group.join('\n'));
    }
  });
  $(el).empty().append(result);
}


/**
 * Display the diff for a single file.
 * @param {string} contentsBefore
 * @param {string} contentsAfter
 * @param {!HTMLDivElement} An unattached div containing the rendered diff.
 */
function renderDiff(contentsBefore, contentsAfter) {
  var diffDiv = $('<div class="diff"></div>').get(0);

  // From https://github.com/cemerick/jsdifflib
  var baseLines = difflib.stringAsLines(contentsBefore);
  var afterLines = difflib.stringAsLines(contentsAfter);

  // create a SequenceMatcher instance that diffs the two sets of lines
  var sm = new difflib.SequenceMatcher(baseLines, afterLines);

  // get the opcodes from the SequenceMatcher instance
  // opcodes is a list of 3-tuples describing what changes should be made to the base text
  // in order to yield the new text
  var opcodes = sm.get_opcodes();
  var contextSize = 10;

  // build the diff view and add it to the current DOM
  diffDiv.appendChild(diffview.buildView({
      baseTextLines: baseLines,
      newTextLines: afterLines,
      opcodes: opcodes,
      // set the display titles for each resource
      baseTextName: "Before",
      newTextName: "After",
      contextSize: contextSize,
      viewType: 0,  // i.e. two column rather than inline.
      characterDiffs: true
  }));

  return diffDiv;
}


/**
 * Find the diff DOM element corresponding to a comment.
 * @param {!Element} diffEl Element containing the rendered two-column diff.
 * @param {{lineNumber: number, onLeft: boolean}} parsedPosition Output of
 *     parseDiffPosition().
 * @return {Element} DOM element corresponding to that line of the diff, or
 *     null if no match could be made.
 */
function findDomElementForPosition(diffEl, parsedPosition) {
  var lineNumber = parsedPosition.lineNumber;
  var sideClass = parsedPosition.onLeft ? 'before' : 'after';

  var $lineEl = $(diffEl).find('.' + sideClass + '.line-' + lineNumber);
  if ($lineEl.length == 0) {
    console.warn('Unable to display comment on diff', parsedPosition);
    return null;
  } else if ($lineEl.length > 1) {
    console.warn('Multiple matches for diff comment', parsedPosition);
    return null;
  }

  return $lineEl.get(0);
}


/**
 * Returns an unattached div containing a rendered comment.
 * @param {!Comment} comment The comment object.
 * @return {!HTMLDivElement} The rendered comment.
 */
function renderComment(comment) {
  var $div = $('#comment-template').clone().removeAttr('id').show();

  $div.data({
    'id': comment.id,
    'lineNumber': comment.line_number,
    'onLeft': comment.on_left
  });

  $div.find('.user').text(comment.user.login);
  if (comment.user.avatar_url) {
    $div.find('.avatar').attr('src', comment.user.avatar_url + '?s=140');
  }

  $div.find('.updated_at').text(comment.updated_at);
  if (comment.html_url) {
    $div.find('.github-link').attr('href', comment.html_url);
  } else {
    $div.find('.github-link').hide();
  }
  $div.find('.comment-body').html(
      new Showdown.converter().makeHtml(comment.body));
  $div.addClass(comment.is_draft ? 'draft' : 'published');
  if ('is_addressed' in comment) {
    $div.addClass(comment['is_addressed'] ? 'addressed' : 'unaddressed');
  }
  if (comment.user.login != logged_in_user) {
    $div.find('.reply').show();
  }
  if (logged_in_user == pr_owner &&
      comment.user.login != logged_in_user &&
      !comment.is_addressed) {
    $div.find('.done-ack-links').show();
  }
  if (comment.is_draft) {
    $div.find('.discard').show();
  }
  return $div.get(0);
}


/**
 * Check for updates to the current pull request.
 * Displays a "please reload" message if any is found.
 */
function checkForUpdates(owner, repo, pull_number, updated_at) {
  $.post('/check_for_updates', {
    'owner': owner,
    'repo': repo,
    'pull_number': pull_number,
    'updated_at': updated_at
  })
  .success(function(response) {
    if (response != "Update") return;

    $('#refresh-update-available').show();
  });
}


function createCommentBox() {
  return $('#editable-comment-template')
      .clone()
      .removeAttr('id')
      .show()
      .get(0);
}

function addReplyBox(commentEl) {
  var $comment = $(commentEl);
  var id = $comment.data('id');
  var $box = $(createCommentBox())
      .data({
          'inReplyTo': id,
          'lineNumber': $comment.data('lineNumber'),
          'onLeft': $comment.data('onLeft')
      });
  $comment.append($box);
  return $box.get(0);
}

$(function() {
  $(document).on('click', '.draft a.discard', function(e) {
    var $comment = $(this).closest('.inline-comment');
    var id = $comment.data('id');

    $.post('/discard_draft_comment', { 'id': id })
    .success(function(response) {
      if (response == "OK") {
        $comment.remove();
      } else {
        console.warn("Unable to discard comment -- backend error", response);
      }
    })
    .fail(function(err) {
      console.warn("Unable to discard comment -- backend error", err);
    });

    e.preventDefault();
  })

  .on('click', '.reply', function(e) {
    var $comment = $(this).closest('.inline-comment');
    var $box = $(addReplyBox($comment.get(0)));
    $box.find('textarea').focus();
    e.preventDefault();
  })

  .on('click', '.done, .ack', function(e) {
    var msg = $(this).hasClass('done') ? 'Done' :
              $(this).hasClass('ack') ? 'Acknowledged' : '';
    if (!msg) return;

    var $comment = $(this).closest('.inline-comment');
    var $box = $(addReplyBox($comment.get(0)));
    $box.find('textarea').text(msg);
    $box.find('.save-comment').click();
    e.preventDefault();
  });

});
