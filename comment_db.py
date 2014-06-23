"""On-disk database for draft comments.

Draft comments are the one piece of state that gitcritic needs to track.
This should use a real DB, but this was easier to set up on an airplane.

Comment:
    key = (login, owner, repo, number)
    # comments in the DB are always drafts.
    original_commit_id: int
    path: string
    original_position: int
    body: string
    in_repy_to: int  # comment ID
    updated_at: string
"""

import os
import cPickle
import sys
import random
import time
import json
import copy
import logging

class CommentDb(object):
    """Fake DB for draft comments.

    This stores the entire DB as a pickle file on disk."""
    def __init__(self):
        self._db_file = '/tmp/better-git-pr/db.pickle'
        if os.path.exists(self._db_file):
            self._comments = cPickle.load(open(self._db_file))
            logging.info('Loaded %d draft comments.', len(self._comments))
        else:
            self._comments = []

    def _write(self):
        cPickle.dump(self._comments, open(self._db_file, 'wb'))

    def get_draft_comments(self, login, owner, repo, number):
        return copy.deepcopy([x for x in self._comments if
                x['login'] == login and
                x['owner'] == owner and
                x['repo'] == repo and
                x['pull_number'] == number])

    def get_draft_comment_by_id(self, comment_id):
        rs = [x for x in self._comments if
              x['id'] == comment_id]
        if len(rs) == 1:
            return copy.deepcopy(rs[0])
        else:
            return None

    def add_draft_comment(self, login, comment):
        assert 'owner' in comment
        assert 'repo' in comment
        assert 'pull_number' in comment
        assert 'original_commit_id' in comment
        assert 'path' in comment
        assert 'original_position' in comment
        assert 'diff_hunk' in comment
        assert 'body' in comment
        db_comment = {
            'login': login,
            'updated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time())),
            'id': random.randrange(2**32)
        }
        db_comment.update(comment)
        updated = False
        if 'id' in comment:
            for idx, c in enumerate(self._comments):
                if c['id'] == comment['id']:
                    self._comments[idx] = db_comment
                    updated = True
                    break
            if not updated:
                return None
        else:
            self._comments.append(db_comment)
        self._write()
        return copy.deepcopy(db_comment)
    
    def delete_draft_comments(self, comment_ids):
        indices = [i for (i, c) in enumerate(self._comments) if c['id'] in comment_ids]
        results = []
        for index in reversed(indices):
            c = self._comments[index]
            del self._comments[index]
            results.append(c)
        self._write()
        results.reverse()
        return copy.deepcopy(results)

    def githubify_comment(self, comment):
        comment['is_draft'] = True
        comment['user'] = { 'login': comment['login'] }
        del comment['login']
        return comment
