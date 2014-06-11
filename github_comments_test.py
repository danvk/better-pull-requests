import github
import github_comments
import unittest
from mock import patch, MagicMock

_ = ''  # a "don't care" value

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
            position, diff_hunk = github_comments.lineNumberToDiffPositionAndHunk(
                    _, _, _, _, _, _, 58, False)
            self.assertEquals(58, position)
            self.assertEquals('@@ -0,0 +1,59 @@', diff_hunk.split('\n')[0])

    def test_lineNumberToDiffPositionAndHunkSmallDiff(self):
        mock = MagicMock(return_value=open('testdata/small-inline.diff.txt').read())
        with patch('github.get_file_diff', mock):
            position, diff_hunk = github_comments.lineNumberToDiffPositionAndHunk(
                    _, _, _, _, _, _, 33, False)
            self.assertEquals(4, position)
            self.assertEquals('@@ -30,6 +30,7 @@', diff_hunk.split('\n')[0])


if __name__ == '__main__':
    unittest.main()
