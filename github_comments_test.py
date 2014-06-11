import github
import github_comments
import unittest
from mock import patch, MagicMock

class GithubCommentsTestCase(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_trivial(self):
        self.assertTrue(True)

    def test_lineNumberToDiffPositionAndHunkCreation(self):
        mock = MagicMock(return_value=open('testdata/file-creation.diff.txt').read())
        with patch('github.get_file_diff', mock):
            position, diff_hunk = github_comments.lineNumberToDiffPositionAndHunk('token', 'owner', 'repo', 'base_sha', 'path', 'commit_id', 58, False)

    def test_lineNumberToDiffPositionAndHunkSmallDiff(self):
        mock = MagicMock(return_value=open('testdata/small-inline.diff.txt').read())
        with patch('github.get_file_diff', mock):
            position, diff_hunk = github_comments.lineNumberToDiffPositionAndHunk('token', 'owner', 'repo', 'base_sha', 'path', 'commit_id', 33, False)



if __name__ == '__main__':
    unittest.main()
