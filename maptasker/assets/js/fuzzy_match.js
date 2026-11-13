// fuzzy_match.js: rank a list of options against what the user typed, for the Font pulldown.
//
// Plain script, no module syntax, so a page can load it with a <script> tag and a test can require() it.
// It defines window.mtFuzzy (and module.exports under Node).
//
// An option matches in one of five ways, best first, and the results come back in that order -- so typing
// 'ari' puts Arial and Arial Black ahead of Avenir, which is a looser match but still offered:
//   0  the label starts with what was typed            'ari'   -> Arial
//   1  a word in the label starts with it              'bla'   -> Arial Black
//   2  it appears somewhere inside                      'rial'  -> Arial
//   3  the first letters of its words, or one slip in    'tnr'   -> Times New Roman
//      the first letters of a word                       'ariel' -> Arial   (a slip only when 4 or more letters are typed)
//   4  its letters appear in order, close together,      'avnr'  -> Avenir  (only when 3 or more are typed)
//      starting at the beginning of a word
// Case, accents, spaces, hyphens and underscores are ignored.  Ties keep the order they came in, which for the fonts is
// monospaced first.
//
// When nothing matches well, one more try is made without a file extension and the style words a font file name ends
// in, so 'Menlo-Regular.ttf' finds Menlo and 'Arial-Bold' finds Arial.  That is done only when what was typed has no
// match better than a near miss, so a family name with a style word in it ('Arial Black') is found as typed.
(function (root) {
  "use strict";

  var EXTENSION = /\.(ttf|otf|ttc|otc|dfont|woff2?)$/;
  var STYLE_WORDS = [
    "regular", "roman", "book", "normal", "bold", "semibold", "demibold", "extrabold", "ultrabold",
    "italic", "oblique", "light", "extralight", "ultralight", "medium", "thin", "black", "heavy",
  ];
  var LOOSE = 3; // the tier from which a match is a near miss rather than a match
  var MIN_TYPO = 4;
  var MIN_SCATTER = 3;
  var SCATTER_SPAN = 2; // the matched letters may spread over at most this many times the letters typed

  function fold(text) {
    return String(text)
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLocaleLowerCase();
  }

  // Whether a word is made of style words, the last of them perhaps only started (the user may be part way through
  // typing it): 'bold', 'bolditalic' and 'boldit' all are.
  function isStyleStart(word) {
    if (!word) return true;
    for (var s = 0; s < STYLE_WORDS.length; s++) {
      if (STYLE_WORDS[s].indexOf(word) === 0) return true;
      if (word.indexOf(STYLE_WORDS[s]) === 0 && isStyleStart(word.slice(STYLE_WORDS[s].length))) return true;
    }
    return false;
  }

  // What was typed without its file extension and the style words on the end of it: 'Menlo-Regular.ttf' -> 'menlo'.
  function withoutFileParts(typed) {
    var rest = fold(typed).trim().replace(EXTENSION, "");
    var parts;
    while ((parts = /^(.*?)[\s\-_.]+([a-z]+)$/.exec(rest)) && isStyleStart(parts[2])) rest = parts[1];
    return rest.trim();
  }

  function wordsOf(label) {
    return label.split(/[^a-z0-9]+/).filter(Boolean);
  }

  // Whether two strings are the same, or differ by one letter changed, added, dropped or swapped with its neighbour.
  function withinOne(a, b) {
    if (a === b) return true;
    var la = a.length;
    var lb = b.length;
    if (Math.abs(la - lb) > 1) return false;
    var i = 0;
    while (i < la && i < lb && a[i] === b[i]) i++;
    if (la === lb) {
      if (a.slice(i + 1) === b.slice(i + 1)) return true; // one letter changed
      return a[i] === b[i + 1] && a[i + 1] === b[i] && a.slice(i + 2) === b.slice(i + 2); // two swapped
    }
    return la > lb ? a.slice(i + 1) === b.slice(i) : b.slice(i + 1) === a.slice(i);
  }

  function nearAWordStart(words, needle) {
    for (var w = 0; w < words.length; w++) {
      for (var len = needle.length - 1; len <= needle.length + 1; len++) {
        if (len > 0 && len <= words[w].length && withinOne(words[w].slice(0, len), needle)) return true;
      }
    }
    return false;
  }

  // How closely the needle's letters, in order, sit together when the first is the start of a word: the span they
  // cover in the label with its spaces taken out, or -1 for no match.  Starts are where the words begin in that label.
  function scatterSpan(squashed, starts, needle) {
    var best = -1;
    for (var s = 0; s < starts.length; s++) {
      if (squashed[starts[s]] !== needle[0]) continue;
      var at = starts[s];
      var ok = true;
      for (var n = 1; n < needle.length; n++) {
        at = squashed.indexOf(needle[n], at + 1);
        if (at === -1) {
          ok = false;
          break;
        }
      }
      if (ok && (best === -1 || at - starts[s] + 1 < best)) best = at - starts[s] + 1;
    }
    return best;
  }

  // [tier, tiebreak] for one label, or null when it does not match.
  function score(needle, label) {
    var text = fold(label);
    var words = wordsOf(text);
    var squashed = text.replace(/[^a-z0-9]+/g, "");
    if (text.indexOf(needle) === 0 || squashed.indexOf(needle.replace(/\s+/g, "")) === 0) return [0, 0];
    for (var w = 0; w < words.length; w++) if (words[w].indexOf(needle) === 0) return [1, w];
    var inside = text.indexOf(needle);
    if (inside !== -1) return [2, inside];
    var squeezed = needle.replace(/\s+/g, "");
    if (squashed.indexOf(squeezed) !== -1) return [2, squashed.indexOf(squeezed)];
    if (words.length > 1 && words.map(function (word) { return word[0]; }).join("").indexOf(squeezed) === 0) return [3, 0];
    if (needle.length >= MIN_TYPO && nearAWordStart(words, squeezed)) return [3, 1];
    if (squeezed.length >= MIN_SCATTER) {
      var starts = [];
      var offset = 0;
      for (var k = 0; k < words.length; k++) {
        starts.push(offset);
        offset += words[k].length;
      }
      var span = scatterSpan(squashed, starts, squeezed);
      if (span !== -1 && span <= squeezed.length * SCATTER_SPAN) return [4, span];
    }
    return null;
  }

  // The matches for one piece of typing, best first, each with the tier it matched at.
  function rank(needle, options) {
    var hits = [];
    for (var i = 0; i < options.length; i++) {
      var found = score(needle, options[i].label);
      if (found) hits.push({ option: options[i], tier: found[0], tiebreak: found[1], index: i });
    }
    return hits.sort(function (a, b) {
      return a.tier - b.tier || a.tiebreak - b.tiebreak || a.index - b.index;
    });
  }

  function optionsOf(hits) {
    return hits.map(function (hit) {
      return hit.option;
    });
  }

  function solid(hits) {
    return hits.length > 0 && hits[0].tier < LOOSE;
  }

  // The options (objects with a label) that match what was typed, best match first.
  function filter(typed, options) {
    var needle = fold(typed).replace(/[-_]+/g, " ").trim();
    if (!needle) return options;
    var hits = rank(needle, options);
    if (solid(hits)) return optionsOf(hits);
    // Nothing matched well as typed: try it as a file name, without its extension and style.
    var bare = withoutFileParts(typed).replace(/[-_]+/g, " ");
    var barehits = bare && bare !== needle ? rank(bare, options) : [];
    return optionsOf(solid(barehits) ? barehits : hits);
  }

  var api = { filter: filter, score: score };
  root.mtFuzzy = api;
  if (typeof module === "object" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
