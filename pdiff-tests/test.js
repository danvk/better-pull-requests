var pdifftest = require('./lib/pdifftest');

// 1 = number of tests in this suite.
casper.test.begin('dygraphs 296', 1, function(test) {
  casper.options.viewportSize = {width: 1280, height: 800};
  // This sequence just configures the test, it doesn't run it.
  pdifftest.startTest(casper, 'http://localhost:5000/danvk/dygraphs/pull/296', function() {
    // ... click things ...

    var screenshot = pdifftest.takeScreenshot(casper);
    pdifftest.checkAgainstGolden(casper, screenshot, 'pdiff-tests/golden/dygraphs-296.png');
  });

  // Until you call "test.done()", the test will hang!
  casper.run(function() {
    test.done();
  });
});
