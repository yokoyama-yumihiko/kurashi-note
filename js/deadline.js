// くらしの制度：期限までの残り日数を、見ている日（日本時間）で表示する
document.addEventListener("DOMContentLoaded", function () {
  var now = new Date(Date.now() + 9 * 3600 * 1000);
  var today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  document.querySelectorAll("[data-deadline]").forEach(function (el) {
    var p = el.getAttribute("data-deadline").split("-");
    var days = Math.round((Date.UTC(+p[0], +p[1] - 1, +p[2]) - today) / 86400000);
    if (isNaN(days) || days < 0) return;
    var badge = document.createElement("span");
    badge.className = "kurashi-left" + (days <= 7 ? " is-soon" : "");
    badge.textContent = days === 0 ? "今日まで" : "あと" + days + "日";
    el.appendChild(badge);
  });
});
