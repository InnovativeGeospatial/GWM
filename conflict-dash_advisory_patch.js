/* =====================================================================
 * PATCH for conflict-dash.js
 * Replaces the STALE embedded State Dept array with a live jsDelivr fetch.
 *
 * WHAT TO REPLACE:
 * In the current conflict-dash.js, find the section that begins with the
 * embedded advisory array (search for a line containing:
 *     STATE_DEPT_ADVISORIES
 * or
 *     var cAdvisories = [
 * or a big hardcoded block like:
 *     {country:"Afghanistan",level:4,...},
 *     {country:"Belarus",   level:4,...},
 *     ...and so on
 *
 * DELETE that entire embedded array + the render block that follows it
 * (the code that iterates over the array and builds the #c-index HTML
 * and updates the L1/L2/L3/L4 stat counts).
 *
 * THEN paste the block below in its place.
 * ===================================================================== */

// ---------------------------------------------------------------------
// State Department Travel Advisories — live feed, served via jsDelivr
// Source JSON is refreshed by the conflict pipeline each run.
// ---------------------------------------------------------------------
var C_ADVISORY_URL =
  "https://cdn.jsdelivr.net/gh/InnovativeGeospatial/GWM@main/travel_advisories.json";

var cAdvisories = [];
var cAdvisoryFilter = 0; // 0 = all, 1-4 = filter by level

function cLevelLabel(n) {
  return [
    "", "Level 1 – Normal", "Level 2 – Caution",
    "Level 3 – Reconsider", "Level 4 – Do Not Travel"
  ][n] || "";
}

function cLevelClass(n) {
  // matches existing panel color scheme: L4=red, L3=orange, L2=yellow, L1=green
  return ["", "low", "med", "high", "crit"][n] || "";
}

function cCountryFlagEmoji(country) {
  // Optional: if you have a flag lookup already in this file, you can call it
  // here. Otherwise return "" — the advisory still renders, just without a flag.
  if (typeof cFlagFor === "function") {
    try { return cFlagFor(country) || ""; } catch (e) {}
  }
  return "";
}

function cRenderAdvisories() {
  var el = document.getElementById("c-index");
  if (!el) return;

  var list = cAdvisories;
  if (cAdvisoryFilter) {
    list = list.filter(function (a) { return a.level === cAdvisoryFilter; });
  }

  if (!list.length) {
    el.innerHTML =
      "<div class='c-row' style='opacity:.6;padding:14px;'>" +
        "No advisories match this filter." +
      "</div>";
    return;
  }

  var html = "";
  for (var i = 0; i < list.length; i++) {
    var a = list[i];
    var cls = cLevelClass(a.level);
    var flag = cCountryFlagEmoji(a.country);
    var pct = (a.level / 4) * 100;
    html +=
      "<div class='c-row' data-level='" + a.level + "' " +
           "title='" + (a.summary || "").replace(/'/g, "&#39;").slice(0, 300) + "'>" +
        "<div class='c-rank'>L" + a.level + "</div>" +
        "<div class='c-flag'>" + flag + "</div>" +
        "<div class='c-info'>" +
          "<div class='c-name'>" + a.country + "</div>" +
          "<div class='c-type'>" + cLevelLabel(a.level) + "</div>" +
        "</div>" +
        "<div class='c-score'>" +
          "<div class='c-score-val " + cls + "'>" + a.level + "</div>" +
          "<div class='c-bar-wrap'>" +
            "<div class='c-bar " + cls + "' style='width:" + pct + "%'></div>" +
          "</div>" +
        "</div>" +
      "</div>";
  }
  el.innerHTML = html;
}

function cRenderAdvisoryStats(counts, updatedAt) {
  // Fills any element with id c-count-L1 .. c-count-L4 if present.
  // If your stat boxes use different IDs, adjust here.
  [1, 2, 3, 4].forEach(function (lvl) {
    var box = document.getElementById("c-count-L" + lvl);
    if (box) box.textContent = counts[lvl] || 0;
  });

  var stamp = document.getElementById("c-advisory-updated");
  if (stamp && updatedAt) {
    try {
      var d = new Date(updatedAt);
      stamp.textContent = "Updated " + d.toUTCString();
    } catch (e) {
      stamp.textContent = "Updated " + updatedAt;
    }
  }
}

// Wire up any L1/L2/L3/L4 filter buttons if present.
// Each button should carry data-advisory-level="1".."4" or "0" for all.
function cWireAdvisoryFilters() {
  var btns = document.querySelectorAll("[data-advisory-level]");
  for (var i = 0; i < btns.length; i++) {
    (function (b) {
      b.addEventListener("click", function () {
        cAdvisoryFilter = parseInt(b.getAttribute("data-advisory-level"), 10) || 0;
        var group = document.querySelectorAll("[data-advisory-level]");
        for (var j = 0; j < group.length; j++) group[j].classList.remove("active");
        b.classList.add("active");
        cRenderAdvisories();
      });
    })(btns[i]);
  }
}

// Fetch + render
(function loadAdvisories() {
  // cache-bust lightly so jsDelivr's 12h edge cache doesn't pin old data after
  // a pipeline run. jsDelivr ignores unknown query params for file contents.
  var url = C_ADVISORY_URL + "?t=" + Math.floor(Date.now() / (1000 * 60 * 30));

  fetch(url)
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(function (payload) {
      cAdvisories = payload.advisories || [];
      cRenderAdvisoryStats(payload.counts || {}, payload.updated_at);
      cRenderAdvisories();
      cWireAdvisoryFilters();
    })
    .catch(function (err) {
      console.error("[conflict-dash] Advisory fetch failed:", err);
      var el = document.getElementById("c-index");
      if (el) {
        el.innerHTML =
          "<div class='c-row' style='opacity:.6;padding:14px;'>" +
            "Advisory data unavailable. " +
            "<a href='https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories.html' " +
               "target='_blank' rel='noopener' style='color:#ef4444;'>" +
              "View on State Dept site" +
            "</a>" +
          "</div>";
      }
    });
})();
