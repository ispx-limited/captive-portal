// While quarantined, the portal's /healthz is always reachable. After payment,
// authmesh CoAs the session back to the working VRF and this box becomes
// unreachable - so consecutive probe failures mean service is restored.
(function () {
  "use strict";

  var FAILURES_NEEDED = 2;
  var INTERVAL_MS = 8000;
  var failures = 0;

  var card = document.getElementById("card");
  var statusText = document.getElementById("status-text");

  function restored() {
    card.classList.add("restored");
    document.getElementById("icon").textContent = "✅";
    document.getElementById("title").textContent = "Your service is restored";
    document.getElementById("message").textContent =
      "Payment received - your connection is active again. " +
      "You may need to reconnect or restart your router.";
    statusText.textContent = "Back online";
  }

  function probe() {
    fetch("/healthz?" + Date.now(), { cache: "no-store" })
      .then(function () {
        failures = 0;
        statusText.textContent = "Waiting for payment — checking automatically";
        setTimeout(probe, INTERVAL_MS);
      })
      .catch(function () {
        failures += 1;
        if (failures >= FAILURES_NEEDED) {
          restored();
        } else {
          setTimeout(probe, INTERVAL_MS);
        }
      });
  }

  setTimeout(probe, INTERVAL_MS);
})();
