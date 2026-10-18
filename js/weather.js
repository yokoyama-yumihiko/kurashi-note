// 今日の天気・注意報/警報・お洗濯の目安（気象庁の公開データを、見ている人のブラウザで直接読む）
// 藤沢市・寒川町は、気象庁の予報区で「神奈川県 東部（湘南）」。気温は横浜の予想。
(function () {
  var box = document.getElementById("weather");
  if (!box) return;
  var BASE = "https://www.jma.go.jp/bosai/";
  var TOWNS = { "1420500": "藤沢市", "1432100": "寒川町" };
  // 気象庁の注意報・警報のコード（わからないコードは「注意報・警報」とだけ出す）
  var NAMES = {
    "02": "暴風雪警報", "03": "大雨警報", "04": "洪水警報", "05": "暴風警報", "06": "大雪警報",
    "07": "波浪警報", "08": "高潮警報", "10": "大雨注意報", "12": "大雪注意報", "13": "風雪注意報",
    "14": "雷注意報", "15": "強風注意報", "16": "波浪注意報", "17": "融雪注意報", "18": "洪水注意報",
    "19": "高潮注意報", "20": "濃霧注意報", "21": "乾燥注意報", "22": "なだれ注意報", "23": "低温注意報",
    "24": "霜注意報", "25": "着氷注意報", "26": "着雪注意報", "32": "暴風雪特別警報", "33": "大雨特別警報",
    "35": "暴風特別警報", "36": "大雪特別警報", "37": "波浪特別警報", "38": "高潮特別警報"
  };
  var WD = "日月火水木金土";

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }
  // 日時は気象庁の文字列（日本時間）から直接読む。海外から見ても日付がずれないように
  function dayLabel(iso) {
    var y = +iso.slice(0, 4), m = +iso.slice(5, 7), d = +iso.slice(8, 10);
    return m + "/" + d + "（" + WD[new Date(Date.UTC(y, m - 1, d)).getUTCDay()] + "）";
  }
  function hourOf(iso) { return +iso.slice(11, 13); }
  function dateKey(iso) { return iso.slice(0, 10); }
  function icon(code) {
    var c = String(code).charAt(0);
    return c === "1" ? "sun" : c === "2" ? "cloud" : c === "4" ? "snow" : "rain";
  }
  // 傘の目安：日中の降水確率と天気の種類から
  function umbrella(code, pop) {
    var c = String(code).charAt(0);
    if (pop === null) return "";
    if (c === "3" || c === "4" || pop >= 50) return "傘を持って";
    if (pop >= 30) return "折りたたみ傘があると安心";
    return "傘はいらなそう";
  }
  // お洗濯の目安：日中（6時〜18時）の降水確率のいちばん高い値と、天気の種類から
  function laundry(code, pop) {
    var c = String(code).charAt(0);
    if (pop === null) return "";
    if (c === "3" || c === "4" || pop > 50) return "洗濯は部屋干しに";
    if (pop > 30) return "洗濯は部屋干しが安心";
    if (c === "1" && pop <= 20) return "洗濯物がよく乾きそう";
    return "外干しできそう";
  }

  Promise.all([
    fetch(BASE + "forecast/data/forecast/140000.json").then(function (r) { return r.json(); }),
    fetch(BASE + "warning/data/warning/140000.json").then(function (r) { return r.json(); })
  ]).then(function (res) {
    var fc = res[0][0], wn = res[1];
    var ts = fc.timeSeries;
    var wx = ts[0].areas.filter(function (a) { return a.area.code === "140010"; })[0];
    var pops = ts[1].areas.filter(function (a) { return a.area.code === "140010"; })[0];
    var temps = ts[2].areas.filter(function (a) { return a.area.name === "横浜"; })[0];

    // 日ごとの日中の降水確率（最大）と気温
    var popBy = {}, tmin = {}, tmax = {};
    ts[1].timeDefines.forEach(function (t, i) {
      var h = hourOf(t), v = pops.pops[i];
      if (h >= 6 && h < 18 && v !== "") popBy[dateKey(t)] = Math.max(popBy[dateKey(t)] || 0, +v);
    });
    ts[2].timeDefines.forEach(function (t, i) {
      var h = hourOf(t);
      if (h === 0) tmin[dateKey(t)] = temps.temps[i];
      if (h === 9) tmax[dateKey(t)] = temps.temps[i];
    });

    // 明日の分で短期予報にない値は、週間予報（1日の降水確率・横浜の気温）で補う
    var week = res[0][1], wPop = {}, wMin = {}, wMax = {};
    if (week) {
      week.timeSeries[0].timeDefines.forEach(function (t, i) {
        var v = week.timeSeries[0].areas[0].pops[i];
        if (v !== "") wPop[dateKey(t)] = +v;
      });
      var wt = week.timeSeries[1].areas.filter(function (a) { return a.area.name === "横浜"; })[0];
      if (wt) week.timeSeries[1].timeDefines.forEach(function (t, i) {
        if (wt.tempsMin[i] !== "") wMin[dateKey(t)] = wt.tempsMin[i];
        if (wt.tempsMax[i] !== "") wMax[dateKey(t)] = wt.tempsMax[i];
      });
    }

    // 日本時間の今日より前の日（夜中に見たときの「きのう」）は出さない
    var now = new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);
    var idx = ts[0].timeDefines.map(function (t, i) { return i; })
      .filter(function (i) { return dateKey(ts[0].timeDefines[i]) >= now; }).slice(0, 2);
    // 1日分を1行にまとめる（今日は大きめ、明日は小さく）
    var days = idx.map(function (i, n) {
      var t = ts[0].timeDefines[i];
      var k = dateKey(t), pop = popBy.hasOwnProperty(k) ? popBy[k] : null;
      if (pop === null && wPop.hasOwnProperty(k)) pop = wPop[k];
      if (!tmax[k] && wMax[k]) tmax[k] = wMax[k];
      if (!tmin[k] && wMin[k]) tmin[k] = wMin[k];
      var code = wx.weatherCodes[i];
      var temp = (tmax[k] ? '<b class="wx-max">' + esc(tmax[k]) + "℃</b>" : "") +
                 (tmin[k] && tmin[k] !== tmax[k] ? '<span class="wx-min">/' + esc(tmin[k]) + "℃</span>" : "");
      var chips = [umbrella(code, pop), laundry(code, pop)].filter(Boolean)
        .map(function (c) { return '<span class="wx-chip">' + esc(c) + "</span>"; }).join("");
      return '<div class="wx-row' + (n ? " is-next" : "") + '">' +
        '<span class="wx-icon" style="-webkit-mask-image:url(assets/icons/wx_' + icon(code) + '.svg);mask-image:url(assets/icons/wx_' + icon(code) + '.svg)" aria-hidden="true"></span>' +
        '<div class="wx-main"><p><strong>' + (k === now ? "今日" : "明日") + "</strong> " + esc(dayLabel(t)) + " " +
        esc(wx.weathers[i].replace(/[\u3000 ]+/g, "").replace(/(.)所により/g, "$1、所により")) + "</p>" +
        '<p class="wx-sub">' + temp + (pop !== null ? '<span class="wx-pop">降水 ' + pop + "%</span>" : "") + "</p>" +
        (chips ? '<p class="wx-chips">' + chips + "</p>" : "") + "</div></div>";
    }).join("");

    // 注意報・警報（藤沢市・寒川町それぞれ。発表・継続中のものだけ）
    var alerts = [];
    wn.areaTypes.forEach(function (at) {
      at.areas.forEach(function (ar) {
        if (!TOWNS[ar.code]) return;
        var list = ar.warnings.filter(function (w) { return w.status === "発表" || w.status === "継続"; })
          .map(function (w) { return NAMES[w.code] || "注意報・警報"; });
        if (list.length) alerts.push({ town: TOWNS[ar.code], list: list });
      });
    });
    var alertHtml = alerts.length
      ? alerts.map(function (a) {
          var strong = a.list.some(function (n) { return n.indexOf("警報") >= 0; });
          return '<p class="wx-alert' + (strong ? " is-warning" : "") + '"><strong>' + esc(a.town) + "</strong>" +
            esc(a.list.join("・")) + "</p>";
        }).join("")
      : '<p class="wx-calm">注意報・警報：いまは出ていません</p>';

    box.innerHTML = alertHtml + days +
      '<p class="wx-note">気温は横浜の予想。傘・お洗濯は気象庁の天気と降水確率からこのサイトが計算した目安。' +
      '出典：<a href="https://www.jma.go.jp/bosai/forecast/#area_type=class20s&area_code=1420500" target="_blank" rel="noopener">気象庁</a>' +
      "（" + esc(dayLabel(fc.reportDatetime)) + hourOf(fc.reportDatetime) + "時発表）</p>";
  }).catch(function () {
    box.innerHTML = '<p class="wx-note">天気を読み込めませんでした。' +
      '<a href="https://www.jma.go.jp/bosai/forecast/#area_type=class20s&area_code=1420500" target="_blank" rel="noopener">気象庁の天気予報</a>' +
      "・<a href=\"https://www.jma.go.jp/bosai/warning/#area_type=class20s&area_code=1420500\" target=\"_blank\" rel=\"noopener\">注意報・警報</a>で確かめてください。</p>";
  });
})();
