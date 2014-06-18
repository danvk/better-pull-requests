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

        if (response.own_prs) {
          console.log(response.own_prs);
          $.each(response.own_prs, function(_, pr) {
            $(ownPullRequestsEl).append($('<div>').text(pr.title));
          });
        }
      });
  });
}
