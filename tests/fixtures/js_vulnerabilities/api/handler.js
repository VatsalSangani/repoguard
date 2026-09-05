// Fixture: prototype-pollution-prone dynamic property assignment.
"use strict";

function mergeSettings(target, updates) {
  for (const key in updates) {
    target[key] = updates[key];
  }
  return target;
}

module.exports = { mergeSettings };
