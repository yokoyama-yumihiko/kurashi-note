// 日本語の改行を文節で区切る（BudouX）。「ニュ／ース」のような言葉の途中での改行を防ぐ。
// 長い複合語（「藤沢市くらし応援カード」など）は、漢字・カタカナの切れ目でさらに区切る。
// 読み込めないときは、今までどおりの改行のまま表示される。
import { loadDefaultJapaneseParser } from "https://cdn.jsdelivr.net/npm/budoux@0.9.3/+esm";

var parser = loadDefaultJapaneseParser();
var SEL = "main h1, main h2, main h3, main p, main li, main dt, main dd, main figcaption, main a, header h1, header p, footer h2, footer p";
var LONG = 7;

function kind(c) {
  if (/[一-鿿々]/.test(c)) return "kanji";
  if (/[゠-ヿ]/.test(c)) return "kata";
  if (/[぀-ゟ]/.test(c)) return "hira";
  if (/[A-Za-z0-9０-９]/.test(c)) return "latin";
  return "other";
}

// 長いかたまりだけ、字の種類が変わる所で区切る（送りがなは前に、「年・月・日」などは数字につける）
function splitLong(chunk) {
  if (chunk.length <= LONG) return [chunk];
  var out = [chunk[0]];
  for (var i = 1; i < chunk.length; i++) {
    var a = kind(chunk[i - 1]), b = kind(chunk[i]);
    // 数字のあとの「年・月・日」などは数字につける
    if (a !== b && a !== "other" && a !== "latin" && b !== "hira" && b !== "other") out.push(chunk[i]);
    else out[out.length - 1] += chunk[i];
  }
  return out;
}

function applyTo(el) {
  var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  var nodes = [];
  while (walker.nextNode()) if (walker.currentNode.nodeValue.trim()) nodes.push(walker.currentNode);
  nodes.forEach(function (node) {
    var parts = [];
    parser.parse(node.nodeValue).forEach(function (c) { parts = parts.concat(splitLong(c)); });
    if (parts.length < 2) return;
    var frag = document.createDocumentFragment();
    parts.forEach(function (p, i) {
      if (i) frag.appendChild(document.createElement("wbr"));
      frag.appendChild(document.createTextNode(p));
    });
    node.replaceWith(frag);
  });
  el.style.wordBreak = "keep-all";
  el.style.overflowWrap = "anywhere";
}

function apply(root) {
  root.querySelectorAll(SEL).forEach(function (el) {
    if (el.closest("[data-lb]")) return;
    el.dataset.lb = "1";
    applyTo(el);
  });
}

apply(document);

// 天気（js/weather.js）は後から書き込まれるので、書き込まれたら区切り直す
var wx = document.getElementById("weather");
if (wx) new MutationObserver(function () { apply(wx); }).observe(wx, { childList: true });
