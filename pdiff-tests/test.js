var pdifftest = require('./lib/pdifftest');

// 1 = number of tests in this suite.
casper.test.begin('dygraphs 296', 1, function(test) {
  casper.options.viewportSize = {width: 1500, height: 768};
  // This sequence just configures the test, it doesn't run it.
  pdifftest.startTest(casper, 'http://localhost:5000/danvk/dygraphs/pull/296?force_token=12345', function() {
    // ... click things ...

    // The page is quite tall -- tall enough that pdiffy hangs on it!
    // We restrict to the top 1024px to speed things up.
    var screenshot = pdifftest.takeScreenshot(casper);
    pdifftest.checkAgainstGolden(casper, screenshot, 'pdiff-tests/golden/dygraphs-296.png');
  });

  // Until you call "test.done()", the test will hang!
  casper.run(function() {
    test.done();
  });
});
