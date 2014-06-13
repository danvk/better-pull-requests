function displayDiffs(before_ref, after_ref, baseTxt, afterTxt) {
  var diffDiv = renderDiff(baseTxt, afterTxt);

  $('#thediff').append(diffDiv);

  var comments = _.filter(diff_comments, function(comment) {
      return (comment.original_commit_id == after_ref ||
              comment.original_commit_id == before_ref) &&
          comment.path == path;
  });

  comments.map(
      function(x) { return attachComment(before_ref, after_ref, diffDiv, x) });
}

function attachComment(before_ref, after_ref, diffDiv, comment) {
  var pos = parseDiffPosition(comment.diff_hunk, comment.position_in_diff_hunk);
  if (comment.original_commit_id == before_ref) {
    pos.onLeft = !pos.onLeft;
  }
  comment.on_left = pos.onLeft;
  comment.line_number = pos.lineNumber;

  var lineEl = findDomElementForPosition(diffDiv, pos);
  $(lineEl).append(renderComment(comment));
}

function appendCommentBox(onLeft, lineNumber) {
  var $box = $(createCommentBox())
      .data({
          'lineNumber': lineNumber,
          'onLeft': onLeft
      });

  var $td = $('td.' + (onLeft ? 'before' : 'after') + '.line-' + lineNumber);
  $td.append($box);
  return $box;
}

function attachHandlers() {
  $('#show-diff').on('click', function() {
    $(this).closest('form').submit();
  });

  $(document).on('keydown', function(e) {
    if (e.ctrlKey || e.altKey || e.metaKey ||
        e.target.tagName.toLowerCase() == 'input' ||
        e.target.tagName.toLowerCase() == 'textarea') {
      return;
    }
    if (e.keyCode == 74 || e.keyCode == 75) {  // j/k
      var klass = (e.keyCode == 74 ? 'next' : 'prev');
      // Any better way to visit links?
      var url = $('a.' + klass).attr('href');
      if (url) {
        window.location = url;
      }
    } else if (e.keyCode == 78) { // n
      // next comment
    } else if (e.keyCode == 80) { // p
      // previous comment
    } else if (e.keyCode == 85) { // u
      window.location = pull_request_url;
    }
    // console.log(e.keyCode);
  });

  $('.diff td, .diff th').on('dblclick', function(e) {
      var $target = $(e.target);
      var td = this;

      if (this.tagName == 'TH') {
        td = $(this).next('td').get(0);
        $target = $(td);
      }

      // Click has to be on the code, not another comment.
      if ($target.closest('.inline-comment').length > 0) return;

      // Should only have one draft at a time.
      var $textarea = $target.closest('td').find('textarea');
      if ($textarea.length > 0) {
        $textarea.focus();
        e.preventDefault();
        return;
      }

      var onLeft = $target.is('.before');
      var lineClasses = td.classList;
      var lineNumber;
      for (var i = 0; i < lineClasses.length; i++) {
        var m = /line-([0-9]+)/.exec(lineClasses[i]);
        if (m) {
          lineNumber = m[1];
          break;
        }
      }
      if (lineNumber === undefined) return;
      var $box = appendCommentBox(onLeft, lineNumber);
      e.preventDefault();
      $box.find('textarea').focus();
      return false;
  });

  $(document).on('click', '.save-comment', function(e) {
      var $comment = $(this).parent('.inline-editable-comment');
      var lineNumber = $comment.data('lineNumber');
      var commitId = $comment.data('onLeft') ? sha1 : sha2;
      var inReplyTo = $comment.data('inReplyTo');
      var body = $comment.find('textarea').val();

      $.ajax({
        dataType: 'json',
        type: 'POST',
        url: '/save_draft',
        data: {
          owner: owner,
          repo: repo,
          pull_number: pr_number,
          path: path,
          commit_id: commitId,
          line_number: lineNumber,
          in_reply_to: inReplyTo,
          body: body,
        }
      }).success(function(comment) {
        $comment.remove();
        diff_comments.push(comment);
        attachComment(sha1, sha2, $('#thediff').get(0), comment);
        // Really we should recompute addressed/unaddressed here.
        if (inReplyTo) {
          $('.inline-comment').filter(function(_, x) { return $(x).data('id')==inReplyTo}).addClass('addressed').removeClass('unaddressed');
        }
      }).error(function(err) {
        console.error(err);
        alert("Unable to post comment!\n\n" + JSON.stringify(err));
      });
  }).on('click', '.discard-comment', function(e) {
      // TODO(danvk): save draft comment at this location.
      var $comment = $(this).parent('.inline-editable-comment');
      $comment.remove();
  });
}
