// Fixture: unsafe dynamic evaluation of user input.
"use strict";

function parseExpression(userInput) {
  const trimmed = userInput.trim();
  let value;

  value = eval(trimmed);
  return value;
}

module.exports = { parseExpression };
