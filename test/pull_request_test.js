function assertEqual(a, b, message) {
  if (!_.isEqual(a, b)) {
    var fullMessage = message + ' Expected ' + a + ' == ' + b;
    console.error('Expected', a, '==', b, message);
    document.body.innerHTML += '<p>' + fullMessage + '</p>\n';
    throw fullMessage;
  }
}

function testInLine() {
  var diffHunk = [
      "@@ -38,8 +38,14 @@ Dygraph.Interaction.startPan = function(event, g, context) {",
      "   var i, axis;",
      "   context.isPanning = true;",
      "   var xRange = g.xAxisRange();",
      "-  context.dateRange = xRange[1] - xRange[0];",
      "-  context.initialLeftmostDate = xRange[0];",
      "+",
      "+  if (g.getOptionForAxis(\"logscale\", 'x')) {"
      ].join('\n');
  var position = 7;

  assertEqual({lineNumber: 42, onLeft: false},
      parseDiffPosition(diffHunk, position));
}


function testOffEnd() {
  var diffHunk = [
      "@@ -183,11 +184,15 @@ DygraphLayout.prototype.evaluate = function() {",
      " ",
      " DygraphLayout.prototype._evaluateLimits = function() {",
      "   var xlimits = this.dygraph_.xAxisRange();",
      "-  this.minxval = xlimits[0];",
      "-  this.maxxval = xlimits[1];",
      "+  this._xAxis.minxval = xlimits[0];",
      ].join('\n');
  var position = 14;

  assertEqual({lineNumber: 187, onLeft: false},
      parseDiffPosition(diffHunk, position));
}


function testOnLeft() {
  var diffHunk = [
    "@@ -1521,16 +1576,6 @@ Dygraph.prototype.doZoomX_ = function(lowX, highX) {",
    " };",
    " ",
    " /**",
    "- * Transition function to use in animations. Returns values between 0.0",
    "- * (totally old values) and 1.0 (totally new values) for each frame.",
    "- * @private",
    "- */",
    "-Dygraph.zoomAnimationFunction = function(frame, numFrames) {",
    ].join("\n");
  var position = 140;

  assertEqual({lineNumber: 1528, onLeft: true},
      parseDiffPosition(diffHunk, position));
}


function runTests() {
  var num_passed = 0;
  for (var k in window) {
    var v = window[k];
    if (k.substr(0, 4) == "test" && typeof(v) == "function") {
      window[k]();
      num_passed += 1;
    }
  }
  document.body.innerHTML += '<p>' + num_passed + ' tests passed</p>\n';
}
runTests();
