var pdifftest = require('./lib/pdifftest');

// 1 = number of tests in this suite.
casper.test.begin('inline comments', 1, function(test) {
  casper.options.viewportSize = {width: 1280, height: 800};
  // This sequence just configures the test, it doesn't run it.
  pdifftest.startTest(casper, 'http://localhost:5000/danvk/dygraphs/pull/296/diff?sha2=335011fd4473f55aaaceb69726d15e0063373149&sha1=01275da4c4f66755dbcef3df7a45ffece4ba2a9b&path=dygraph-layout.js', function() {
    // ... click things ...

    // The page is quite tall -- tall enough that pdiffy hangs on it!
    // We restrict to the top 2000px to speed things up.
    var screenshot = pdifftest.takeScreenshot(casper, {left:0, top:0, width:1280, height:2000});
    pdifftest.checkAgainstGolden(casper, screenshot, 'pdiff-tests/golden/inline-comments.png');
  });

  // Until you call "test.done()", the test will hang!
  casper.run(function() {
    test.done();
  });
});
