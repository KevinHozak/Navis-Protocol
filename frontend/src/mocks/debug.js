function debugMock() {
  return function() {};
}
debugMock.coerce = () => {};
debugMock.disable = () => {};
debugMock.enable = () => {};
debugMock.enabled = () => false;
debugMock.humanize = () => {};
debugMock.names = [];
debugMock.skips = [];
debugMock.formatters = {};

module.exports = debugMock;
