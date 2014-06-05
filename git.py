"""This should be eliminated entirely!

get_differing_files:
    GET /repos/:owner/:repo/compare/sha1...sha2
    Differing files are in files.filename.
    This also includes diffstats.

get_file_at_ref(path, ref):
    GET /repos/:owner/:repo/contents/path&ref=...
    -H "Accept: application/vnd.github.3.raw"

get_file_diff(path, sha1, sha2):
    GET /repos/:owner/:repo/compare/sha1...sha2
    -H "Accept: application/vnd.github.3.diff"
    Then split the output into per-file diffs.

"""
import tempfile
import subprocess
import os
import sys
import re
import hashlib

TEMP_DIR = '/tmp/better-git-pr'  # make a new temporary directory
GIT = '/usr/bin/git'

if not os.path.exists(TEMP_DIR):
    os.mkdir(TEMP_DIR)

CLONE_URL_TO_DIR = {}


def _dir_for_clone_url(clone_url):
    """Returns a predictable directory path based on clone_url."""
    if clone_url not in CLONE_URL_TO_DIR:
        md5 = hashlib.md5(clone_url).hexdigest()
        repo_name = humanish_repo_name(clone_url)
        d = os.path.join(TEMP_DIR, '%s.%s' % (repo_name, md5))
        CLONE_URL_TO_DIR[clone_url] = d
    return CLONE_URL_TO_DIR[clone_url]


def humanish_repo_name(clone_url):
    return os.path.splitext(os.path.basename(clone_url))[0]


def clone_repo(clone_url):
    """Returns a path to the newly-cloned repo."""

    git_dir = _dir_for_clone_url(clone_url)
    sys.stderr.write('git dir for %s = %s\n' % (clone_url, git_dir))
    if os.path.exists(git_dir):
        # We've already cloned it. Pull instead.
        pr = subprocess.Popen(['/usr/bin/git', 'pull'],
               cwd=git_dir,
               stdout=subprocess.PIPE, 
               stderr=subprocess.PIPE, 
               shell=False)
        (stdout, stderr) = pr.communicate()
        sys.stderr.write(stderr)

    else:
        sys.stderr.write('Cloning %s into %s\n' % (clone_url, git_dir))
        pr = subprocess.Popen(['/usr/bin/git', 'clone', clone_url, git_dir],
               cwd=TEMP_DIR,
               stdout=subprocess.PIPE, 
               stderr=subprocess.PIPE, 
               shell=False)
        (stdout, stderr) = pr.communicate()
        sys.stderr.write(stderr)

    if os.path.exists(git_dir):
        return git_dir
    return None


def _does_sha_exist(clone_url, sha):
    if clone_url not in CLONE_URL_TO_DIR:
        return False

    d = CLONE_URL_TO_DIR[clone_url]
    if not os.path.exists(d):
        return False

    pr = subprocess.Popen(['/usr/bin/git', 'show', sha],
           cwd=d,
           stdout=subprocess.PIPE, 
           stderr=subprocess.PIPE, 
           shell=False)
    (stdout, stderr) = pr.communicate()
    return pr.returncode == 0


def _clone_if_no_sha(clone_url, sha):
    if not _does_sha_exist(clone_url, sha):
        clone_repo(clone_url)
    if not _does_sha_exist(clone_url, sha):
        sys.stderr.write('Unable to get %s from %s\n' % (sha, clone_url))
        return False
    return True


def get_differing_files(clone_url, sha1, sha2):
    if not (_clone_if_no_sha(clone_url, sha1) and _clone_if_no_sha(clone_url, sha2)):
        return False

    d = CLONE_URL_TO_DIR[clone_url]

    pr = subprocess.Popen(['/usr/bin/git', 'diff', '--name-only', sha1, sha2],
           cwd=d,
           stdout=subprocess.PIPE, 
           stderr=subprocess.PIPE, 
           shell=False)
    (stdout, stderr) = pr.communicate()
    sys.stderr.write(stderr)
    if pr.returncode != 0:
        return None

    return [x for x in stdout.split('\n') if x]


def get_file_at_ref(clone_url, path, ref):
    if not _clone_if_no_sha(clone_url, ref):
        return False

    d = CLONE_URL_TO_DIR[clone_url]
    pr = subprocess.Popen(['/usr/bin/git', 'show', '%s:%s' % (ref, path)],
           cwd=d,
           stdout=subprocess.PIPE, 
           stderr=subprocess.PIPE, 
           shell=False)
    (stdout, stderr) = pr.communicate()
    sys.stderr.write(stderr)
    if pr.returncode != 0:
        return None
    return stdout


def get_file_diff(clone_url, path, sha1, sha2):
    if not (_clone_if_no_sha(clone_url, sha1) and _clone_if_no_sha(clone_url, sha2)):
        return False

    d = CLONE_URL_TO_DIR[clone_url]

    pr = subprocess.Popen(['/usr/bin/git', 'diff', sha1 + '..' + sha2, path],
           cwd=d,
           stdout=subprocess.PIPE, 
           stderr=subprocess.PIPE, 
           shell=False)
    (stdout, stderr) = pr.communicate()
    sys.stderr.write(stderr)
    if pr.returncode != 0:
        return None

    return stdout
