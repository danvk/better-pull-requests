function renderPullRequest(pr) {
  var $prEl = $('#pr-template').clone().removeAttr('id').show();

  $prEl.find('.repo-name').text(pr['base']['repo']['full_name']);
  $prEl.find('.main-link').text(pr['title']).attr('href', pr['url']);
  $prEl.find('.github-link').attr('href', pr['html_url']);

  return $prEl.get(0);
}

function addPullRequestCounts(followedReposEl, ownPullRequestsEl) {
  $(followedReposEl).find('li').each(function(_, el) {
    var owner = $(el).attr('owner');
    var repo = $(el).attr('repo');
    $.post('/count_open_pull_requests', { owner: owner, repo: repo })
      .success(function(response) {
        var count = response.count;
        if (count) {
          $(el).find('.pr-count').text(count + ' open pull request' + (count == 1 ? '' : 's'));
        } else {
          $(el).find('.repo-data').empty();
        }

        if (response.own) {
          $.each(response.own, function(_, pr) {
            $(ownPullRequestsEl).append(renderPullRequest(pr));
          });
        }
      });
  });
}
